from typing import Optional

from embedchain.config.base_config import BaseConfig


class ContextRelevanceConfig(BaseConfig):
    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None, language: str = "en"):
        self.model = model
        self.api_key = api_key
        self.language = language


class AnswerRelevanceConfig(BaseConfig):
    def __init__(
        self,
        model: str = "gpt-4",
        embedder: str = "text-embedding-ada-002",
        api_key: Optional[str] = None,
        num_gen_questions: int = 1,
    ):
        self.model = model
        self.embedder = embedder
        self.api_key = api_key
        self.num_gen_questions = num_gen_questions
