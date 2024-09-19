import os
from typing import Dict, List, Optional

# from openai import OpenAI
import google.generativeai as genai
from google.generativeai.types import content_types

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class GeminiLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "gemini-1.5-flash-latest"

        # if os.environ.get("OPENROUTER_API_KEY"):  # Use OpenRouter
        #     self.client = OpenAI(
        #         api_key=os.environ.get("OPENROUTER_API_KEY"),
        #         base_url=self.config.openrouter_base_url,
        #     )
        # else:
        api_key = self.config.api_key or os.getenv("GEMINI_API_KEY")
        # base_url = os.getenv("OPENAI_API_BASE") or self.config.openai_base_url
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model_name=self.config.model)

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
                "content": response.candidates[0].content,
                "tool_calls": [],
            }

            if response.candidates[0].function_calls:
                for function_call in response.candidates[0].function_calls:
                    processed_response["tool_calls"].append(
                        {
                            "name": function_call.name,
                            "arguments": function_call.args.items(),
                        }
                    )

            return processed_response
        else:
            return response.candidates[0].content

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using OpenAI.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format for the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """
        
        params = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        # if os.getenv("OPENROUTER_API_KEY"):
        #     openrouter_params = {}
        #     if self.config.models:
        #         openrouter_params["models"] = self.config.models
        #         openrouter_params["route"] = self.config.route
        #         params.pop("model")

        #     if self.config.site_url and self.config.app_name:
        #         extra_headers = {
        #             "HTTP-Referer": self.config.site_url,
        #             "X-Title": self.config.app_name,
        #         }
        #         openrouter_params["extra_headers"] = extra_headers

            # params.update(**openrouter_params)

        if response_format:
            params["response_mime_type"] = "applications/json"
            params["response_schema"] = response_format
        if tool_choice:
            tool_config = content_types.to_tool_config(
            {"function_calling_config": 
                {"mode": tool_choice, "allowed_function_names": [x.__name__ for x in tools]}
            })

        response = self.client.generate_content(messages, generation_config=genai.GenerationConfig(**params), tool_config=tool_config)
        # response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
