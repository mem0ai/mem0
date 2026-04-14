import asyncio
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest

from mem0.llms.base import LLMBase


class DummyLLM(LLMBase):
    """A concrete LLM subclass for testing the base class fallback."""

    def generate_response(
        self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None, tool_choice: str = "auto", **kwargs
    ):
        return "sync response"


@pytest.mark.asyncio
async def test_base_agenerate_response_fallback():
    """Test that the base class agenerate_response falls back to asyncio.to_thread."""
    llm = DummyLLM(config={"model": "test-model"})

    with patch("mem0.llms.base.asyncio.to_thread", return_value="sync response") as mock_to_thread:
        mock_to_thread.return_value = "sync response"
        # Make to_thread a coroutine
        async def fake_to_thread(fn, **kwargs):
            return fn(**kwargs)

        with patch("mem0.llms.base.asyncio.to_thread", side_effect=fake_to_thread):
            result = await llm.agenerate_response(messages=[{"role": "user", "content": "hi"}])

    assert result == "sync response"
