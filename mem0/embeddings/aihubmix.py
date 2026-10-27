import copy
import os
from typing import Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings import openai as openai_embedding
from mem0.embeddings.base import EmbeddingBase
from mem0.embeddings.openai import OpenAIEmbedding


class AIHubMixEmbedding(OpenAIEmbedding):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        config = copy.copy(config) if config is not None else BaseEmbedderConfig()
        api_key = config.api_key or os.getenv("AIHUBMIX_API_KEY")
        if not api_key:
            raise ValueError("AIHubMix API key is required: set api_key or AIHUBMIX_API_KEY")
        config.api_key = api_key
        config.openai_base_url = config.aihubmix_base_url or os.getenv("AIHUBMIX_BASE_URL") or "https://aihubmix.com/v1"
        config.model = config.model or "embed-v-4-0"
        EmbeddingBase.__init__(self, config)
        self._pass_dimensions_to_api = self.config.embedding_dims is not None
        self.config.embedding_dims = self.config.embedding_dims or 1536
        self.client = openai_embedding.OpenAI(api_key=api_key, base_url=config.openai_base_url)
