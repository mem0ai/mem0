import json
import os
from typing import Dict, List, Optional

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json

MODELSLAB_BASE_URL = "https://modelslab.com/api/uncensored-chat/v1"
MODELSLAB_DEFAULT_MODEL = "llama-3.1-8b-uncensored"


class ModelsLabLLM(LLMBase):
    """LLM integration for ModelsLab's uncensored chat API.

    ModelsLab (https://modelslab.com) provides an OpenAI-compatible chat
    completion endpoint for uncensored Llama-based models with 128K context
    windows.  This class uses the standard ``openai`` SDK — no extra
    dependencies required.

    Supported models
    ----------------
    - ``llama-3.1-8b-uncensored``  (128 K context, default)
    - ``llama-3.1-70b-uncensored`` (128 K context)

    Configuration
    -------------
    Pass a :class:`BaseLlmConfig` with:

    - ``model``: model identifier (optional, defaults to ``llama-3.1-8b-uncensored``)
    - ``api_key``: ModelsLab API key (falls back to ``MODELSLAB_API_KEY`` env var)
    - ``temperature``, ``max_tokens``, ``top_p``: standard sampling parameters

    Quick start
    -----------
    .. code-block:: python

        from mem0 import Memory

        config = {
            "llm": {
                "provider": "modelslab",
                "config": {
                    "model": "llama-3.1-70b-uncensored",
                    "api_key": "<your-modelslab-api-key>",  # or set MODELSLAB_API_KEY
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
            },
        }

        m = Memory.from_config(config)
        m.add("I prefer dark mode in all my apps.", user_id="alice")
        result = m.search("What are Alice's UI preferences?", user_id="alice")
        print(result)

    Get an API key at https://modelslab.com/api-keys
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = MODELSLAB_DEFAULT_MODEL

        api_key = self.config.api_key or os.getenv("MODELSLAB_API_KEY")
        if not api_key:
            raise ValueError(
                "ModelsLab API key is required.  Pass it via the 'api_key' config field "
                "or set the MODELSLAB_API_KEY environment variable.  "
                "Get your key at https://modelslab.com/api-keys"
            )

        self.client = OpenAI(api_key=api_key, base_url=MODELSLAB_BASE_URL)

    def _parse_response(self, response, tools):
        """Process the response based on whether tools are used or not.

        Args:
            response: The raw response from the ModelsLab API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: Plain text content, or a dict with ``content`` and
            ``tool_calls`` keys when tools were used.
        """
        if tools:
            processed_response = {
                "content": response.choices[0].message.content,
                "tool_calls": [],
            }

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    processed_response["tool_calls"].append(
                        {
                            "name": tool_call.function.name,
                            "arguments": json.loads(extract_json(tool_call.function.arguments)),
                        }
                    )

            return processed_response
        else:
            return response.choices[0].message.content

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """Generate a response using the ModelsLab chat completion API.

        Args:
            messages (list): List of message dicts with 'role' and 'content' keys.
            response_format (str or object, optional): Response format override.
            tools (list, optional): Tool definitions the model may call.
            tool_choice (str, optional): Tool selection strategy.  Defaults to
                ``"auto"``.

        Returns:
            str | dict: The model's response text, or a dict with tool call
            information when ``tools`` are provided.
        """
        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if response_format:
            params["response_format"] = response_format

        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
