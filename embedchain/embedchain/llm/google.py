import logging
import os
from typing import Optional

try:
    from google import genai
except ImportError:
    raise ImportError("GoogleLlm requires extra dependencies. Install with `pip install google-genai`") from None

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm

logger = logging.getLogger(__name__)


@register_deserializable
class GoogleLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)
        if not self.config.api_key and "GOOGLE_API_KEY" not in os.environ:
            raise ValueError("Please set the GOOGLE_API_KEY environment variable or pass it in the config.")
        self.client = genai.Client(api_key=self.config.api_key or os.getenv("GOOGLE_API_KEY"))

    def get_llm_model_answer(self, prompt):
        model_name = self.config.model or "gemini-2.5-flash"
        logger.info(f"Using Google LLM model: {model_name}")

        config = genai.types.GenerateContentConfig(
            temperature=self.config.temperature or None,
            top_p=self.config.top_p or None,
            candidate_count=1,
            max_output_tokens=self.config.max_tokens or None,
            system_instruction=self.config.system_prompt or None,
        )

        if self.config.stream:
            responses = self.client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=config,
            )
            return (response.text for response in responses)

        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        return response.text
