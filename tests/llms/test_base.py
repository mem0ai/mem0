"""Tests for LLMBase reasoning-model classification.

Covers the o4 family (o4-mini and dated aliases), which was previously
classified as a regular model so temperature/top_p/max_tokens were sent
despite being unsupported on reasoning models.
"""

import pytest

from mem0.llms.base import LLMBase


class _MinimalLLM(LLMBase):
    def generate_response(self, messages, tools=None, tool_choice="auto", **kwargs):
        return ""


@pytest.mark.parametrize(
    "model, expected",
    [
        ("o4-mini", True),
        ("o4-mini-2025-04-16", True),
        ("openai/o4-mini", True),
        ("O4-Mini", True),
        ("o3-mini", True),
        ("o3-2025-04-16", True),
        ("o1-2024-12-17", True),
        ("gpt-4o-mini", False),
        ("gpt-5.4-mini", False),
    ],
)
def test_is_reasoning_model(model, expected):
    llm = _MinimalLLM()
    assert llm._is_reasoning_model(model) is expected
