# Chinese LLM Adapters for Mem0 (Qwen · Zhipu · Moonshot)

This branch adds first-class support for three leading Chinese LLM providers to
Mem0's Python SDK, so Chinese developers can use Mem0 with their preferred
domestic models without writing custom adapters.

| Provider | Company | Adapter | Default Model | API Base URL |
| --- | --- | --- | --- | --- |
| `qwen` | Alibaba Cloud (DashScope) | `mem0/llms/qwen.py` | `qwen-plus` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `zhipu` | Zhipu AI (BigModel) | `mem0/llms/zhipu.py` | `glm-4-plus` | `https://open.bigmodel.cn/api/paas/v4` |
| `moonshot` | Moonshot AI (Kimi) | `mem0/llms/moonshot.py` | `kimi-k3` | `https://api.moonshot.cn/v1` |

All three providers expose an OpenAI-compatible API, so the adapters are built
on the same `OpenAI` client used by the existing `deepseek` adapter, keeping the
codebase consistent and easy to review.

---

## What was added

```
mem0/configs/llms/qwen.py        # QwenConfig (adds qwen_base_url)
mem0/configs/llms/zhipu.py       # ZhipuConfig (adds zhipu_base_url)
mem0/configs/llms/moonshot.py    # MoonshotConfig (adds moonshot_base_url)
mem0/llms/qwen.py                # QwenLLM adapter
mem0/llms/zhipu.py               # ZhipuLLM adapter
mem0/llms/moonshot.py            # MoonshotLLM adapter
mem0/llms/configs.py             # register qwen/zhipu/moonshot as valid providers
mem0/utils/factory.py            # wire providers into LlmFactory
tests/llms/test_qwen.py          # 5 unit tests
tests/llms/test_zhipu.py         # 5 unit tests
tests/llms/test_moonshot.py      # 5 unit tests
docs/components/llms/models/qwen.mdx
docs/components/llms/models/zhipu.mdx
docs/components/llms/models/moonshot.mdx
docs/components/llms/config.mdx  # add *_base_url params to the master list
docs/docs.json                   # add provider pages to the docs nav
docs/open-source/configuration.mdx  # add providers to the supported table
```

---

## Quick start

### 1. Qwen (Alibaba Cloud DashScope)

```bash
export DASHSCOPE_API_KEY="sk-..."   # or QWEN_API_KEY
```

```python
from mem0 import Memory

config = {
    "llm": {
        "provider": "qwen",
        "config": {
            "model": "qwen-plus",   # default
            "temperature": 0.1,
            "max_tokens": 2000,
            "top_p": 0.1,
        },
    }
}
m = Memory.from_config(config)
m.add("I love hiking on weekends.", user_id="alice")
```

Custom endpoint:

```python
config = {
    "llm": {
        "provider": "qwen",
        "config": {
            "model": "qwen-plus",
            "qwen_base_url": "https://your-custom-endpoint.com",
            "api_key": "sk-...",   # optional, overrides env var
        },
    }
}
```

### 2. Zhipu AI (GLM)

```bash
export ZHIPU_API_KEY="..."
```

```python
config = {
    "llm": {
        "provider": "zhipu",
        "config": {
            "model": "glm-4-plus",  # default
            "temperature": 0.1,
            "max_tokens": 2000,
            "top_p": 0.1,
        },
    }
}
```

### 3. Moonshot AI (Kimi)

```bash
export MOONSHOT_API_KEY="..."
```

> **Note:** `kimi-k3` is a reasoning model. Its API only accepts
> `temperature=1.0` and `top_p=0.95`. Use these values in the config.

```python
config = {
    "llm": {
        "provider": "moonshot",
        "config": {
            "model": "kimi-k3",     # default
            "temperature": 1.0,     # required for kimi-k3
            "top_p": 0.95,          # required for kimi-k3
            "max_tokens": 2000,
        },
    }
}
```

---

## Configuration reference

| Parameter | Qwen | Zhipu | Moonshot |
| --- | --- | --- | --- |
| `model` | `qwen-plus` (default) | `glm-4-plus` (default) | `kimi-k3` (default) |
| `api_key` | `DASHSCOPE_API_KEY` / `QWEN_API_KEY` | `ZHIPU_API_KEY` | `MOONSHOT_API_KEY` |
| `*_base_url` | `QWEN_API_BASE` | `ZHIPU_API_BASE` | `MOONSHOT_API_BASE` |
| `temperature` | ✓ | ✓ | ✓ (must be `1.0` for `kimi-k3`) |
| `top_p` | ✓ | ✓ | ✓ (must be `0.95` for `kimi-k3`) |
| `top_k` | ✓ | ✓ | ✓ |
| `max_tokens` | ✓ | ✓ | ✓ |

Value precedence (highest first): explicit `config` value → environment
variable → adapter default. This matches the behavior documented in
[Configurations](docs/components/llms/config.mdx).

---

## Running the tests

```bash
pip install -e ".[dev]"

python -m pytest tests/llms/test_qwen.py tests/llms/test_zhipu.py tests/llms/test_moonshot.py -v
```

All 15 unit tests pass. They mock the `OpenAI` client and verify:

- default / env-var / config base-URL resolution,
- parameter forwarding to `chat.completions.create`,
- tool-call parsing (`add_memory`),
- `response_format` handling,
- plain text responses.

### Real API verification

Each adapter was also verified against its live API with a real key:

| Provider | Model | Prompt | Result |
| --- | --- | --- | --- |
| Qwen | `qwen-plus` | `2+3=?` | `5` ✓ |
| Zhipu | `glm-4-plus` | `2+3=?` | `5` ✓ |
| Moonshot | `kimi-k3` | `2+3=?` | `5` ✓ |

---

## Related

- Resolves the feature request in [mem0ai/mem0#4651](https://github.com/mem0ai/mem0/issues/4651)
  (support for Alibaba Cloud's Qwen series).
- Follows the same adapter pattern as the existing
  [DeepSeek adapter](mem0/llms/deepseek.py).
