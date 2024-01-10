from typing import Optional

from embedchain.config.base_config import BaseConfig


class EvalConfig(BaseConfig):
    def __init__(self, model_name: str = "gpt-4", api_key: Optional[str] = None, language: str = "en"):
        self.model_name = model_name
        self.api_key = api_key
        self.language = language
