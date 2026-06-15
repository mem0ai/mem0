"""Static validation of the local-first packaging (task_10 / ADR-001, ADR-003).

We cannot run ``docker compose up`` in unit tests, so these tests validate the
compose contract deterministically by parsing ``openmemory/docker-compose.yml``
and ``openmemory/api/.env.example``. They assert the requirements of task_10:

- the MCP/API service and Qdrant are present and expose their ports;
- the app is wired to the Qdrant container (QDRANT_HOST/PORT) and to a local
  Ollama (OLLAMA_BASE_URL) — the model names come from install-time detection;
- data persists: the Qdrant volume is mounted at its real storage path;
- no dependency on services outside the local network (privacy): every URL-like
  default points at a local/private address.
"""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_API_DIR = Path(__file__).resolve().parents[1]          # openmemory/api
_OPENMEMORY_DIR = _API_DIR.parent                        # openmemory
_COMPOSE = _OPENMEMORY_DIR / "docker-compose.yml"
_ENV_EXAMPLE = _API_DIR / ".env.example"

# Hosts considered local / private (no external dependency).
_LOCAL_HOST_HINTS = (
    "host.docker.internal",
    "localhost",
    "127.0.0.1",
    "mem0_store",
    "0.0.0.0",
)
_PRIVATE_IP = re.compile(r"https?://(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)")


@pytest.fixture(scope="module")
def compose():
    assert _COMPOSE.exists(), f"missing {_COMPOSE}"
    return yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def mcp_env(compose):
    """The openmemory-mcp `environment` list parsed into a dict."""
    env_list = compose["services"]["openmemory-mcp"].get("environment", [])
    env = {}
    for item in env_list:
        if "=" in item:
            k, v = item.split("=", 1)
            env[k] = v
        else:
            env[item] = None  # pass-through from host
    return env


# --------------------------------------------------------------------------- #
# Services + ports
# --------------------------------------------------------------------------- #
class TestServices:
    def test_required_services_present(self, compose):
        services = compose["services"]
        assert "openmemory-mcp" in services
        assert "mem0_store" in services

    def test_qdrant_exposes_6333(self, compose):
        ports = compose["services"]["mem0_store"]["ports"]
        assert any(str(p).startswith("6333:6333") for p in ports)

    def test_api_exposes_8765(self, compose):
        ports = compose["services"]["openmemory-mcp"]["ports"]
        assert any("8765:8765" in str(p) for p in ports)

    def test_api_depends_on_qdrant(self, compose):
        depends = compose["services"]["openmemory-mcp"].get("depends_on", [])
        # depends_on may be a list or a mapping (condition form).
        names = depends if isinstance(depends, list) else list(depends.keys())
        assert "mem0_store" in names


# --------------------------------------------------------------------------- #
# Wiring: Qdrant + Ollama + DB
# --------------------------------------------------------------------------- #
class TestWiring:
    def test_points_at_qdrant_container(self, mcp_env):
        assert mcp_env.get("QDRANT_HOST") == "mem0_store"
        assert mcp_env.get("QDRANT_PORT") == "6333"

    def test_ollama_base_url_present_and_local(self, mcp_env):
        url = mcp_env.get("OLLAMA_BASE_URL", "")
        assert url, "OLLAMA_BASE_URL must be set"
        assert any(h in url for h in _LOCAL_HOST_HINTS) or _PRIVATE_IP.match(url)

    def test_llm_and_embedder_provider_configurable(self, mcp_env):
        # Provider/model envs must be present (model names chosen at install).
        assert "LLM_PROVIDER" in mcp_env
        assert "LLM_MODEL" in mcp_env
        assert "EMBEDDER_PROVIDER" in mcp_env
        assert "EMBEDDER_MODEL" in mcp_env

    def test_database_url_present(self, mcp_env):
        assert "DATABASE_URL" in mcp_env


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
class TestPersistence:
    def test_qdrant_volume_mounted_at_storage_path(self, compose):
        vols = compose["services"]["mem0_store"]["volumes"]
        # Qdrant persists under /qdrant/storage; the named volume must map there
        # so memories survive a container restart.
        assert any(str(v).endswith(":/qdrant/storage") for v in vols)

    def test_named_volume_declared(self, compose):
        assert "mem0_storage" in compose.get("volumes", {})


# --------------------------------------------------------------------------- #
# No external dependencies (privacy)
# --------------------------------------------------------------------------- #
class TestNoExternalDependency:
    def test_no_public_url_in_compose_defaults(self, compose):
        raw = _COMPOSE.read_text(encoding="utf-8")
        urls = re.findall(r"https?://[^\s\"'}$]+", raw)
        for url in urls:
            # Strip ${VAR:-...} default markers if any leaked into the match.
            assert any(h in url for h in _LOCAL_HOST_HINTS) or _PRIVATE_IP.match(url), (
                f"compose references a non-local URL: {url}"
            )


# --------------------------------------------------------------------------- #
# .env.example contract
# --------------------------------------------------------------------------- #
class TestEnvExample:
    def test_env_example_has_required_keys(self):
        text = _ENV_EXAMPLE.read_text(encoding="utf-8")
        for key in (
            "OLLAMA_BASE_URL",
            "QDRANT_HOST",
            "QDRANT_PORT",
            "DATABASE_URL",
            "LLM_PROVIDER",
            "EMBEDDER_PROVIDER",
        ):
            assert key in text, f".env.example missing {key}"
