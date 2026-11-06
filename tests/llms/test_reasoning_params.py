from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class _StubLLM(LLMBase):
    def generate_response(self, messages, tools=None, tool_choice="auto", **kwargs):
        return {}


def _reasoning_llm():
    return _StubLLM(config=BaseLlmConfig(model="o3-mini"))


def test_reasoning_preserves_extra_kwargs():
    llm = _reasoning_llm()
    params = llm._get_supported_params(
        messages=[{"role": "user", "content": "hi"}],
        extra_body={"a": 1},
        seed=42,
        parallel_tool_calls=False,
    )
    assert params["extra_body"] == {"a": 1}
    assert params["seed"] == 42
    assert params["parallel_tool_calls"] is False
    assert params["messages"] == [{"role": "user", "content": "hi"}]


def test_reasoning_still_drops_sampling_params():
    llm = _reasoning_llm()
    params = llm._get_supported_params(messages=[], temperature=0.9, top_p=0.9, top_k=5, seed=1)
    assert "temperature" not in params
    assert "top_p" not in params
    assert "top_k" not in params
    assert params["seed"] == 1
