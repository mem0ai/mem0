from typing import Dict, List, Optional

try:
    from ollama import Client
except ImportError:
    raise ImportError(
        "The 'ollama' library is required. Please install it using 'pip install ollama'."
    )

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class OllamaLLM(LLMBase):
    """
    A class for interacting with Ollama's language models using the specified configuration.
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """
        Initializes the OllamaLLM instance with the given configuration.

        Args:
            config (Optional[BaseLlmConfig]): Configuration settings for the language model.
        """
        super().__init__(config)

        if not self.config.model:
            self.config.model = "llama3.1:70b"

        self.client = Client(host=self.config.ollama_base_url)
        self._ensure_model_exists()

    def _ensure_model_exists(self):
        """
        Ensures the specified model exists locally. If not, pulls it from Ollama.
        """
        local_models = self.client.list()["models"]
        if not any(model.get("name") == self.config.model for model in local_models):
            self.client.pull(self.config.model)

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[str] = None,
    ) -> str:
        """
        Generates a response using Ollama based on the provided messages.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing a 'role' and 'content' key.
            response_format (Optional[str]): The desired format of the response. Defaults to None.

        Returns:
            str: The generated response from the model.
        """
        params = {
            "model": self.config.model,
            "messages": messages,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
                "top_p": self.config.top_p,
            },
        }
        if response_format:
            params["format"] = "json"

        response = self.client.chat(**params)
        return response["message"]["content"]
