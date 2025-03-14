import os
from typing import Dict, List, Optional

try:
    import google.generativeai as genai
    from google.generativeai import GenerativeModel
except ImportError:
    raise ImportError(
        "The 'google-generativeai' library is required. Please install it using 'pip install google-generativeai'."
    )

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class GeminiLLM(LLMBase):
    """
    A wrapper for Google's Gemini language model, integrating it with the LLMBase class.
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """
        Initializes the Gemini LLM with the provided configuration.

        Args:
            config (Optional[BaseLlmConfig]): Configuration object for the model.
        """
        super().__init__(config)

        if not self.config.model:
            self.config.model = "gemini-1.5-flash-latest"

        api_key = self.config.api_key or os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        self.client = GenerativeModel(model_name=self.config.model)

    def _reformat_messages(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Reformats messages to match the Gemini API's expected structure.

        Args:
            messages (List[Dict[str, str]]): A list of messages with 'role' and 'content' keys.

        Returns:
            List[Dict[str, str]]: Reformatted messages in the required format.
        """
        new_messages = []

        for message in messages:
            if message["role"] == "system":
                content = (
                    "THIS IS A SYSTEM PROMPT. YOU MUST OBEY THIS: " + message["content"]
                )
            else:
                content = message["content"]

            new_messages.append(
                {
                    "parts": content,
                    "role": "model" if message["role"] == "model" else "user",
                }
            )

        return new_messages

    def generate_response(
        self, messages: List[Dict[str, str]], response_format: Optional[Dict] = None
    ) -> str:
        """
        Generates a response from Gemini based on the given conversation history.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries containing 'role' and 'content'.
            response_format (Optional[Dict]): Specifies the response format (e.g., JSON schema).

        Returns:
            str: The generated response as text.
        """
        params = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if response_format and response_format.get("type") == "json_object":
            params["response_mime_type"] = "application/json"
            if "schema" in response_format:
                params["response_schema"] = response_format["schema"]

        response = self.client.generate_content(
            contents=self._reformat_messages(messages),
            generation_config=genai.GenerationConfig(**params),
        )

        return response.candidates[0].content.parts[0].text
