import json
from typing import Dict, List, Optional

try:
    import litellm
except ImportError:
    raise ImportError(
        "The 'litellm' library is required. Please install it using 'pip install litellm'."
    )

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class LiteLLM(LLMBase):
    """
    A class for interacting with LiteLLM's language models using the specified configuration.
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """
        Initializes the LiteLLM instance with the given configuration.

        Args:
            config (Optional[BaseLlmConfig]): Configuration settings for the language model.
        """
        super().__init__(config)

        if not self.config.model:
            self.config.model = "gpt-4o-mini"

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[str] = None,
    ) -> str:
        """
        Generates a response using LiteLLM based on the provided messages.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing a 'role' and 'content' key.
            response_format (Optional[str]): The desired format of the response. Defaults to None.

        Returns:
            str: The generated response from the model.
        """
        if not litellm.supports_function_calling(self.config.model):
            raise ValueError(
                f"Model '{self.config.model}' in LiteLLM does not support function calling."
            )

        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }
        if response_format:
            params["response_format"] = response_format

        response = litellm.completion(**params)
        return response.choices[0].message.content
