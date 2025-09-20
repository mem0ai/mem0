import logging
import os
from collections.abc import Generator
from typing import Any, Optional, Union

try:
    from google import genai
    from google.genai import types
except ImportError:
    raise ImportError("The 'google-genai' library is required. Please install it using 'pip install google-genai'.")

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

        self.api_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key)

    def get_llm_model_answer(self, prompt):
        response = self._get_answer(prompt)
        return response

    def _get_answer(self, prompt: str) -> Union[str, Generator[Any, Any, None]]:
        model_name = self.config.model or "gemini-2.5-flash"
        logger.info(f"Using Google LLM model: {model_name}")
        
        generation_config = {
            "candidate_count": 1,
             "max_output_tokens": self.config.max_tokens,
             "temperature": self.config.temperature or 0.5,
        }

        if 0.0 <= self.config.top_p <= 1.0:
            generation_config["top_p"] = self.config.top_p
        else:
            raise ValueError("`top_p` must be > 0.0 and < 1.0")
        
        if self.config.system_prompt:
            generation_config["system_prompt"] = self.config.system_prompt

        config = types.GenerateContentConfig(**generation_config)  
        """ types.GenerateContentConfig(
                 thinking_config=types.ThinkingConfig(thinking_budget=0) # Disables thinking
            ),
            By defualt thinking is enabled. Need to implement a config option to enable/disable it.
        """

        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        if self.config.stream:
            response = self.client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=config,
            )
            
        else:
            return response.text
