"""Tests for the SSRF guard on ollama_base_url in the OpenMemory config API.

Regression coverage for https://github.com/mem0ai/mem0/issues/6081: the
config endpoints accepted an arbitrary ``ollama_base_url`` with no scheme or
IP-range validation, allowing an unauthenticated caller to point the server at
internal addresses (e.g. the cloud metadata endpoint).
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from pydantic import ValidationError

from app.routers.config import EmbedderConfig, LLMConfig
from app.utils.url_validation import UnsafeURLError, validate_public_base_url


# ---------------------------------------------------------------------------
# validate_public_base_url unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # AWS IMDS (the reported PoC)
        "http://127.0.0.1:11434",  # loopback
        "http://localhost:11434",  # loopback by name
        "http://10.0.0.5:11434",  # private RFC1918
        "http://192.168.1.10:11434",  # private RFC1918
        "http://172.16.0.1:11434",  # private RFC1918
        "http://[::1]:11434",  # IPv6 loopback
        "file:///etc/passwd",  # disallowed scheme
        "ftp://example.com",  # disallowed scheme
        "not-a-url",  # no scheme/host
        "",  # empty
    ],
)
def test_validate_public_base_url_rejects_unsafe(url):
    with pytest.raises(UnsafeURLError):
        validate_public_base_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8:11434",  # public IP literal
        "https://1.1.1.1",  # public IP literal (no DNS needed)
    ],
)
def test_validate_public_base_url_allows_public(url):
    assert validate_public_base_url(url) == url


# ---------------------------------------------------------------------------
# pydantic model integration
# ---------------------------------------------------------------------------

def test_llm_config_rejects_ssrf_ollama_url():
    with pytest.raises(ValidationError):
        LLMConfig(
            model="llama3.1",
            temperature=0.1,
            max_tokens=2000,
            ollama_base_url="http://169.254.169.254/latest/meta-data/",
        )


def test_embedder_config_rejects_ssrf_ollama_url():
    with pytest.raises(ValidationError):
        EmbedderConfig(
            model="nomic-embed-text",
            ollama_base_url="http://127.0.0.1:11434",
        )


def test_llm_config_allows_none_ollama_url():
    cfg = LLMConfig(model="gpt-4o-mini", temperature=0.1, max_tokens=2000)
    assert cfg.ollama_base_url is None
