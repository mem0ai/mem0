"""
Tests for the Groq documentation content added in PR:
  - GROQ_BASE_URL configuration guidance
  - Warning about /openai/v1 path duplication
"""
import os
import re

import pytest

GROQ_DOCS_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "docs",
    "components",
    "llms",
    "models",
    "groq.mdx",
)


@pytest.fixture(scope="module")
def groq_docs_content():
    with open(GROQ_DOCS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_groq_docs_file_exists():
    """The Groq documentation file must exist."""
    assert os.path.isfile(GROQ_DOCS_PATH), f"Documentation file not found: {GROQ_DOCS_PATH}"


def test_groq_base_url_instruction_present(groq_docs_content):
    """The docs must contain an instruction block about setting GROQ_BASE_URL."""
    assert "GROQ_BASE_URL" in groq_docs_content, (
        "Expected GROQ_BASE_URL configuration guidance to be present in groq.mdx"
    )


def test_groq_base_url_value_is_api_groq_com(groq_docs_content):
    """The documented GROQ_BASE_URL value must be https://api.groq.com (without /openai/v1)."""
    assert "GROQ_BASE_URL=https://api.groq.com" in groq_docs_content, (
        "Expected 'GROQ_BASE_URL=https://api.groq.com' to appear in groq.mdx"
    )


def test_groq_base_url_does_not_include_openai_v1(groq_docs_content):
    """The recommended GROQ_BASE_URL must NOT include /openai/v1 as a suffix.

    The docs explicitly warn against this, and the recommended value should reflect it.
    """
    # Extract the line(s) that set GROQ_BASE_URL
    base_url_lines = [
        line.strip()
        for line in groq_docs_content.splitlines()
        if line.strip().startswith("GROQ_BASE_URL=")
    ]
    assert base_url_lines, "No GROQ_BASE_URL= assignment line found in groq.mdx"
    for line in base_url_lines:
        assert not line.rstrip("/").endswith("/openai/v1"), (
            f"Documented GROQ_BASE_URL must not end with /openai/v1, but found: {line!r}"
        )


def test_groq_docs_warns_against_openai_v1_path(groq_docs_content):
    """The docs must explicitly warn users NOT to include /openai/v1 in the base URL."""
    assert "/openai/v1" in groq_docs_content, (
        "Expected a warning mentioning '/openai/v1' to be present in groq.mdx"
    )
    # The text "Avoid" should appear near the /openai/v1 mention
    avoid_pattern = re.compile(r"Avoid.*?/openai/v1", re.DOTALL)
    assert avoid_pattern.search(groq_docs_content), (
        "Expected an 'Avoid ... /openai/v1' warning in groq.mdx"
    )


def test_groq_docs_mentions_404_errors(groq_docs_content):
    """The docs must mention that incorrect base URL configuration can cause 404 errors."""
    assert "404" in groq_docs_content, (
        "Expected a mention of '404 errors' in the GROQ_BASE_URL warning in groq.mdx"
    )


def test_groq_docs_mentions_internal_path_appending(groq_docs_content):
    """The docs must explain that Mem0 internally appends the required path segment."""
    assert "internally appends" in groq_docs_content, (
        "Expected docs to state that Mem0 'internally appends' the required path"
    )


def test_groq_docs_mentions_duplicated_endpoints(groq_docs_content):
    """The docs must warn about duplicated endpoints when /openai/v1 is included."""
    assert "duplicated" in groq_docs_content.lower() or "duplicate" in groq_docs_content.lower(), (
        "Expected a warning about duplicated/duplicate endpoints in groq.mdx"
    )


def test_groq_docs_openai_compatible_clients_context(groq_docs_content):
    """The GROQ_BASE_URL note must be scoped to OpenAI-compatible client usage."""
    assert "OpenAI-compatible" in groq_docs_content, (
        "Expected the GROQ_BASE_URL guidance to be scoped to 'OpenAI-compatible clients' in groq.mdx"
    )


def test_groq_docs_ends_with_newline():
    """The docs file must end with a newline (fixed in this PR)."""
    with open(GROQ_DOCS_PATH, "rb") as f:
        content = f.read()
    assert content.endswith(b"\n"), (
        "groq.mdx must end with a newline character"
    )


def test_groq_base_url_not_full_openai_endpoint(groq_docs_content):
    """Regression: the recommended GROQ_BASE_URL must NOT be the full OpenAI v1 endpoint.

    Users should set GROQ_BASE_URL=https://api.groq.com, not
    GROQ_BASE_URL=https://api.groq.com/openai/v1.
    """
    # Ensure the incorrect full endpoint is not shown as the recommended value
    incorrect_url = "GROQ_BASE_URL=https://api.groq.com/openai/v1"
    assert incorrect_url not in groq_docs_content, (
        f"Incorrect base URL '{incorrect_url}' must not appear as a recommended value in groq.mdx"
    )