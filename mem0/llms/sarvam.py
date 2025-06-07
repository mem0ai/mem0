import os
import requests
from typing import Dict, List, Optional
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class SarvamLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        # Set default model if not provided
        if not self.config.model:
            self.config.model = "sarvam-m"

        # Get API key from config or environment variable
        self.api_key = self.config.api_key or os.getenv("SARVAM_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Sarvam API key is required. Set SARVAM_API_KEY environment variable " "or provide api_key in config."
            )

        # Set base URL - use config value or environment or default
        self.base_url = (
            getattr(self.config, "sarvam_base_url", None) or os.getenv("SARVAM_API_BASE") or "https://api.sarvam.ai/v1"
        )

    def generate_response(self, messages: List[Dict[str, str]], response_format=None) -> str:
        """
        Generate a response based on the given messages using Sarvam-M.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response.
                                                     Currently not used by Sarvam API.

        Returns:
            str: The generated response.
        """
        url = f"{self.base_url}/chat/completions"

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # Prepare the request payload
        params = {
            "messages": messages,
            "model": self.config.model if isinstance(self.config.model, str) else "sarvam-m",
        }

        # Add standard parameters that already exist in BaseLlmConfig
        if self.config.temperature is not None:
            params["temperature"] = self.config.temperature

        if self.config.max_tokens is not None:
            params["max_tokens"] = self.config.max_tokens

        if self.config.top_p is not None:
            params["top_p"] = self.config.top_p

        # Handle Sarvam-specific parameters if model is passed as dict
        if isinstance(self.config.model, dict):
            # Extract model name
            params["model"] = self.config.model.get("name", "sarvam-m")

            # Add Sarvam-specific parameters
            sarvam_specific_params = ["reasoning_effort", "frequency_penalty", "presence_penalty", "seed", "stop", "n"]

            for param in sarvam_specific_params:
                if param in self.config.model:
                    params[param] = self.config.model[param]

        try:
            response = requests.post(url, headers=headers, json=params, timeout=30)
            response.raise_for_status()

            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                raise ValueError("No response choices found in Sarvam API response")

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Sarvam API request failed: {e}")
        except KeyError as e:
            raise ValueError(f"Unexpected response format from Sarvam API: {e}")
