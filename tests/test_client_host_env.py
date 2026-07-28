from unittest.mock import MagicMock, patch

import pytest


def _ping_response():
    response = MagicMock()
    response.json.return_value = {
        "org_id": "org-test",
        "project_id": "project-test",
        "user_email": "test@example.com",
    }
    response.raise_for_status.return_value = None
    return response


@pytest.fixture(autouse=True)
def isolate_host_environment(monkeypatch):
    monkeypatch.delenv("MEM0_HOST", raising=False)
    monkeypatch.delenv("MEM0_API_URL", raising=False)
    monkeypatch.setenv("MEM0_API_KEY", "test-api-key")


def test_memory_client_prefers_explicit_host_over_environment(monkeypatch):
    monkeypatch.setenv("MEM0_HOST", "https://host.example.com")
    monkeypatch.setenv("MEM0_API_URL", "https://api-url.example.com")

    with (
        patch("mem0.client.main.httpx.Client") as client_factory,
        patch("mem0.client.main.capture_client_event"),
    ):
        client_factory.return_value.get.return_value = _ping_response()
        from mem0.client.main import MemoryClient

        client = MemoryClient(host="https://explicit.example.com")

    assert client.host == "https://explicit.example.com"
    assert client_factory.call_args.kwargs["base_url"] == "https://explicit.example.com"


@pytest.mark.parametrize(
    ("host_env", "api_url_env", "expected"),
    [
        ("https://host.example.com", "https://api-url.example.com", "https://host.example.com"),
        (None, "https://api-url.example.com", "https://api-url.example.com"),
        (None, None, "https://api.mem0.ai"),
    ],
)
def test_memory_client_resolves_host_from_environment(
    monkeypatch, host_env, api_url_env, expected
):
    if host_env is not None:
        monkeypatch.setenv("MEM0_HOST", host_env)
    if api_url_env is not None:
        monkeypatch.setenv("MEM0_API_URL", api_url_env)

    with (
        patch("mem0.client.main.httpx.Client") as client_factory,
        patch("mem0.client.main.capture_client_event"),
    ):
        client_factory.return_value.get.return_value = _ping_response()
        from mem0.client.main import MemoryClient

        client = MemoryClient()

    assert client.host == expected
    assert client_factory.call_args.kwargs["base_url"] == expected


def test_async_memory_client_uses_the_same_environment_precedence(monkeypatch):
    monkeypatch.setenv("MEM0_HOST", "https://host.example.com")
    monkeypatch.setenv("MEM0_API_URL", "https://api-url.example.com")

    with (
        patch("mem0.client.main.httpx.AsyncClient") as client_factory,
        patch("mem0.client.main.requests.get", return_value=_ping_response()),
        patch("mem0.client.main.capture_client_event"),
    ):
        from mem0.client.main import AsyncMemoryClient

        client = AsyncMemoryClient()

    assert client.host == "https://host.example.com"
    assert client_factory.call_args.kwargs["base_url"] == "https://host.example.com"
