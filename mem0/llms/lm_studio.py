import json
from typing import Dict, List, Optional

from openai import OpenAI

from mem0.llms.base import LLMBase
from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.prompts import FUNCTION_CALLING_PROMPT


class LMStudioLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "lmstudio-community/Meta-Llama-3.1-70B-Instruct-GGUF/Meta-Llama-3.1-70B-Instruct-IQ2_M.gguf"
        self.config.api_key = self.config.api_key or "lm-studio"
        
        self.client = OpenAI(base_url=self.config.lmstudio_base_url, api_key=self.config.api_key)  
    
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
                "tool_calls": []
            }
    
            tool_calls = json.loads(response.choices[0].message.content)
            
            for tool_call in tool_calls["function_calls"]:
                if tool_call["name"] == "update_memory" or tool_call["name"] == "delete_memory":
                    if tool_call["parameters"]["memory_id"] == "":
                        continue
                processed_response["tool_calls"].append({
                    "name": tool_call["name"],
                    "arguments": tool_call["parameters"]
                })
            
            return processed_response
        else:
            return response.choices[0].message.content

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: dict = {"type": "json_object"},
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto"
    ):
        """
        Generate a response based on the given messages using LM Studio.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """
        params = {
            "model": self.config.model, 
            "messages": messages, 
            "temperature": self.config.temperature, 
            "max_tokens": self.config.max_tokens, 
            "top_p": self.config.top_p
        }
            
        if tools:
            params["response_format"] = response_format
            system_prompt =  {
                "role": "system",
                "content": FUNCTION_CALLING_PROMPT
            }
            params["messages"].insert(0, system_prompt)

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
