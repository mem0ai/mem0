import json
from typing import Dict, List, Optional, Union

try:
    from ollama import Client
except ImportError:
    raise ImportError("The 'ollama' library is required. Please install it using 'pip install ollama'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.ollama import OllamaConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class OllamaLLM(LLMBase):
    def __init__(self, config: Optional[Union[BaseLlmConfig, OllamaConfig, Dict]] = None):
        # Convert to OllamaConfig if needed
        if config is None:
            config = OllamaConfig()
        elif isinstance(config, dict):
            config = OllamaConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, OllamaConfig):
            # Convert BaseLlmConfig to OllamaConfig
            config = OllamaConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=config.enable_vision,
                vision_details=config.vision_details,
                http_client_proxies=config.http_client,
            )

        super().__init__(config)

        if not self.config.model:
            self.config.model = "llama3.1:70b"

        self.client = Client(host=self.config.ollama_base_url)

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        # Get the content from response
        if isinstance(response, dict):
            content = response["message"]["content"]
        else:
            content = response.message.content

        if tools:
            processed_response = {
                "content": content,
                "tool_calls": [],
            }

            if isinstance(response, dict):
                raw_calls = response.get("message", {}).get("tool_calls") or []
            else:
                raw_calls = getattr(response.message, "tool_calls", None) or []

            for tool_call in raw_calls:
                if isinstance(tool_call, dict):
                    fn = tool_call.get("function", {})
                    name = fn.get("name", "")
                    arguments = fn.get("arguments", {})
                else:
                    fn = getattr(tool_call, "function", None)
                    name = getattr(fn, "name", "") if fn else ""
                    arguments = getattr(fn, "arguments", {}) if fn else {}

                if isinstance(arguments, str):
                    arguments = json.loads(extract_json(arguments))

                processed_response["tool_calls"].append(
                    {"name": name, "arguments": arguments}
                )

            return processed_response
        else:
            return content

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        """
        Generate a response based on the given messages using Ollama.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional Ollama-specific parameters.

        Returns:
            str: The generated response.
        """
        # Build parameters for Ollama
        params = {
            "model": self.config.model,
            "messages": messages,
        }

        # We intentionally avoid Ollama's native `format="json"` path here.
        # Smaller local models often still wrap the payload in markdown or
        # surround it with extra text, so we rely on `extract_json` instead.

        # Add options for Ollama (temperature, num_predict, top_p)
        options = {
            "temperature": self.config.temperature,
            "num_predict": self.config.max_tokens,
            "top_p": self.config.top_p,
        }
        params["options"] = options

        # Remove OpenAI-specific parameters that Ollama doesn't support
        params.pop("max_tokens", None)  # Ollama uses different parameter names

        if tools:
            params["tools"] = tools

        response = self.client.chat(**params)
        return self._parse_response(response, tools)
