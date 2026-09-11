from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory
from mem0.memory.redaction import REDACTED, redact_secrets

SECRETS = [
    # OpenAI / Anthropic "sk-" convention
    "sk-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKL",
    "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789",
    "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789",
    # AWS access key IDs
    "AKIAIOSFODNN7EXAMPLE",
    "ASIAIOSFODNN7EXAMPLE",
    # GitHub
    "ghp_" + "a" * 36,
    "github_pat_" + "A1b2C3d4E5f6G7h8I9j0K1",
    # Stripe
    "sk_live_abcdefghij1234567890",
    "rk_test_abcdefghij1234567890",
    # Slack
    "xoxb-123456789012-abcdefghijkl",
    # Google
    "AIza" + "B" * 35,
    # JWT
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk",
]

# Shapes that must survive: redacting these would be worse than the problem.
KEEP = [
    "da39a3ee5e6b4b0d3255bfef95601890afd80709",  # git SHA-1
    "I use a risk-based approach to prioritisation",  # contains "sk-"
    "https://api.example.com/v1/users?page=2",  # URI without credentials
    "pk_live_abcdefghij1234567890",  # Stripe publishable key, not a secret
    "AKIAIOSFODNN7",  # too short to be an AWS key id
    "The meeting is at 3pm on Tuesday",
]


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_shapes_are_redacted(secret):
    out = redact_secrets(f"my key is {secret} keep this")
    assert secret not in out
    assert REDACTED in out
    assert out.startswith("my key is ") and out.endswith(" keep this")


@pytest.mark.parametrize("text", KEEP)
def test_non_secrets_are_left_alone(text):
    assert redact_secrets(text) == text


def test_pem_private_key_block_is_redacted():
    text = (
        "here it is\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA1234\nabcd\n"
        "-----END RSA PRIVATE KEY-----\n"
        "that was it"
    )
    out = redact_secrets(text)
    assert "MIIEowIBAAKCAQEA1234" not in out
    assert "BEGIN RSA PRIVATE KEY" not in out
    assert out == f"here it is\n{REDACTED}\nthat was it"


def test_credentialed_uri_keeps_everything_but_the_password():
    out = redact_secrets("postgres://admin:hunter2@db.internal:5432/prod")
    assert out == f"postgres://admin:{REDACTED}@db.internal:5432/prod"


def test_multiple_secrets_in_one_memory():
    out = redact_secrets("AKIAIOSFODNN7EXAMPLE and " + "ghp_" + "b" * 36)
    assert out == f"{REDACTED} and {REDACTED}"


@pytest.mark.parametrize("value", ["", None, 0, [], {"a": 1}])
def test_empty_and_non_string_inputs_pass_through(value):
    assert redact_secrets(value) == value


# --- recall boundary wiring -------------------------------------------------

STORED = "deploy key AKIAIOSFODNN7EXAMPLE for prod"


def _stub_self(redact_recalled_secrets, is_async=False):
    """Minimal stand-in for Memory/AsyncMemory covering what _search_vector_store
    touches, so the wiring is tested without a live store, embedder, or LLM."""
    stub = MagicMock()
    stub.config.redact_recalled_secrets = redact_recalled_secrets
    stub.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    stub.vector_store.keyword_search.return_value = None
    stub.vector_store.search.return_value = [SimpleNamespace(id="m1", score=0.9, payload={"data": STORED, "hash": "h"})]
    if is_async:
        stub._compute_entity_boosts_async = AsyncMock(return_value={})
    else:
        stub._compute_entity_boosts.return_value = {}
    return stub


def test_search_redacts_recalled_memory_by_default():
    results = Memory._search_vector_store(_stub_self(True), "deploy key", {"user_id": "alice"}, 10)

    assert results[0]["memory"] == f"deploy key {REDACTED} for prod"


def test_search_returns_verbatim_when_redaction_is_disabled():
    results = Memory._search_vector_store(_stub_self(False), "deploy key", {"user_id": "alice"}, 10)

    assert results[0]["memory"] == STORED


@pytest.mark.asyncio
async def test_async_search_redacts_recalled_memory_by_default():
    stub = _stub_self(True, is_async=True)

    results = await AsyncMemory._search_vector_store(stub, "deploy key", {"user_id": "alice"}, 10)

    assert results[0]["memory"] == f"deploy key {REDACTED} for prod"
