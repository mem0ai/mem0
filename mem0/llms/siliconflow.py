import json
import os
import requests
from typing import Dict, List, Optional, Any

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class SiliconFlowLLM(LLMBase):
    """
    SiliconFlow chat completion provider.
    Docs:
      https://docs.siliconflow.com/en/api-reference/chat-completions/chat-completions
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "Qwen/Qwen2.5-7B-Instruct"

        self.api_key = self.config.api_key or os.getenv("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise ValueError("SiliconFlow API key not found. Set SILICONFLOW_API_KEY or pass via config.api_key.")

        # Allow override of base URL via config or environment (docs show .com domain)
        self.base_url = (
            getattr(self.config, "base_url", None)
            or os.getenv("SILICONFLOW_BASE_URL")
            or "https://api.siliconflow.com/v1"
        )

        # Pre-build headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _parse_response(self, data: Dict[str, Any], tools: Optional[List[Dict]]) -> Any:
        """
        Matches structure similar to OpenAI-like responses.
        """
        try:
            choice = data["choices"][0]
            message = choice.get("message", {})
        except (KeyError, IndexError):
            raise ValueError(f"Unexpected SiliconFlow response format: {data}")

        if tools:
            processed = {"content": message.get("content"), "tool_calls": []}
            # If SiliconFlow returns tool_calls similar to OpenAI:
            for tc in message.get("tool_calls", []) or []:
                try:
                    name = tc["function"]["name"]
                    raw_args = tc["function"].get("arguments", "{}")
                    # Ensure JSON object parsing
                    args = json.loads(extract_json(raw_args))
                    processed["tool_calls"].append({"name": name, "arguments": args})
                except Exception:
                    # Fallback raw
                    processed["tool_calls"].append(
                        {
                            "name": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments"),
                        }
                    )
            return processed
        else:
            return message.get("content")

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Create chat completion via SiliconFlow.
        Adjust request body keys if docs differ.
        """
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "max_tokens": self.config.max_tokens,
        }

        # Response format (if SiliconFlow supports 'response_format': {"type": "json_object"})
        if response_format:
            payload["response_format"] = response_format

        # Tool / function calling (verify exact schema in docs; may differ)
        if tools:
            payload["tools"] = tools
            # Some APIs expect {"type":"function","function":{...}} structures
            # tool_choice might be "auto" / {"type":"function","function":{"name":"..."}}
            payload["tool_choice"] = tool_choice

        resp = requests.post(self._endpoint(), headers=self.headers, json=payload, timeout=60)
        if resp.status_code >= 400:
            extra_hint = ""
            if resp.status_code == 401:
                extra_hint = (
                    " (401 Unauthorized: Verify SILICONFLOW_API_KEY is correct and matches the domain "
                    f"{self.base_url.split('/v1')[0]}; you can also set SILICONFLOW_BASE_URL if needed)"
                )
            raise RuntimeError(f"SiliconFlow error {resp.status_code}: {resp.text}{extra_hint}")

        data = resp.json()
        return self._parse_response(data, tools)
