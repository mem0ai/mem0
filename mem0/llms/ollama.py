import ollama
from .base import LLMBase
from .base import BaseLlmConfig
from typing import Dict, List, Optional
import json

class OllamaLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        self.model = "llama3"
        if  config.model is not None:
          self.model = config.model
        self._ensure_model_exists()

    def _ensure_model_exists(self):
        """
        Ensure the specified model exists locally. If not, pull it from Ollama.
        """
        model_list = [m["name"] for m in ollama.list()["models"]]
        if not any(m.startswith(self.model) for m in model_list):
            ollama.pull(self.model)
            
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
                "content": response["message"]["content"],
                "tool_calls": []
            }
            
            if response["message"]["tool_calls"]:
                for tool_call in response["message"]["tool_calls"]:
                    processed_response["tool_calls"].append({
                        "name": tool_call["function"]["name"],
                        "arguments": tool_call["function"]["arguments"]
                    })
            
            return processed_response
        else:
            return response["message"]["content"]


    def generate_response(self, 
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",):
        """
        Generate a response based on the given messages using Ollama.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.

        Returns:
            str: The generated response.
        """
        response = ollama.chat(model=self.model, messages=messages,tools=tools)
        return self._parse_response(response, tools)
