import json
from typing import Dict, List, Optional

try:
    import litellm
except ImportError:
    raise ImportError("litellm requires extra dependencies. Install with `pip install litellm`") from None

from mem0.llms.base import LLMBase
from mem0.configs.llms.base import BaseLlmConfig


class LiteLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model="gpt-4o"
    
    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        if tools:
            processed_response = {
                "content": response.choices[0].message.content,
                "tool_calls": []
            }
            
            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    processed_response["tool_calls"].append({
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments)
                    })
            
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
        """
        Generate a response based on the given messages using Litellm.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """
        if not litellm.supports_function_calling(self.config.model):
            raise ValueError(f"Model '{self.config.model}' in litellm does not support function calling.")

        params = {
            "model": self.config.model, 
            "messages": messages, 
            "temperature": self.config.temperature, 
            "max_tokens": self.config.max_tokens, 
            "top_p": self.config.top_p
        }
        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = litellm.completion(**params)
        return self._parse_response(response, tools)
