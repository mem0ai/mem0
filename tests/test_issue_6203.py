"""Regression test for issue #6203.

Verifies that the OSS TypeScript Anthropic provider does not silently drop the
responseFormat argument when callers request structured JSON output.
"""

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("posthog", MagicMock())
sys.modules.setdefault("qdrant_client", MagicMock())

with patch("importlib.metadata.version", return_value="0.0.0"):
    from mem0 import Memory


def test_issue_6203():
    assert Memory is not None

    provider_path = Path(__file__).resolve().parents[1] / "mem0-ts/src/oss/src/llms/anthropic.ts"
    source = provider_path.read_text()

    match = re.search(r"async generateResponse\([\s\S]*?\n  async generateChat", source)
    assert match, "AnthropicLLM.generateResponse should exist"

    generate_response_source = match.group(0)
    assert "responseFormat?: { type: string }" in generate_response_source

    body_after_signature = generate_response_source.split("): Promise<string | LLMResponse> {", 1)[1]

    assert "responseFormat" in body_after_signature
    assert "json_object" in body_after_signature
    assert "extractJson" in body_after_signature
    assert "json_schema" in body_after_signature
    assert "output_config" in body_after_signature
    assert re.search(r"if \(\s*!responseFormat\s*\)", body_after_signature) or re.search(
        r"if \(\s*responseFormat\s*===\s*undefined\s*\)", body_after_signature
    )
