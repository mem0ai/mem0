from typing import Optional

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class GPT4AllEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        from langchain_community.embeddings import (
            GPT4AllEmbeddings as LangchainGPT4AllEmbeddings,
        )

        model_name = self.config.model or "all-MiniLM-L6-v2-f16.gguf"
        gpt4all_kwargs = {'allow_download': 'True'}
        embeddings = LangchainGPT4AllEmbeddings(model_name=model_name, gpt4all_kwargs=gpt4all_kwargs)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.GPT4ALL.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
