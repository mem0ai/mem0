import json
import os
from typing import Dict, List, Optional

try:
    from groq import Groq
except ImportError:
    raise ImportError(
        "The 'groq' library is required. Please install it using 'pip install groq'."
    )

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class GroqLLM(LLMBase):
    """
    A class for interacting with Groq's language models using the specified configuration.
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """
        Initializes the GroqLLM instance with the given configuration.

        Args:
            config (Optional[BaseLlmConfig]): Configuration settings for the language model.
        """
        super().__init__(config)

        if not self.config.model:
            self.config.model = "llama3-70b-8192"

        api_key = self.config.api_key or os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key)

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[str] = None,
    ) -> str:
        """
        Generates a response using Groq based on the provided messages.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing a 'role' and 'content' key.
            response_format (Optional[str]): The desired format of the response. Defaults to None.

        Returns:
            str: The generated response from the model.
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
        response = self.client.chat.completions.create(**params)
        return response.choices[0].message.content
