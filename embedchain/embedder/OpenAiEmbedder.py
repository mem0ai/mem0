from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.BaseEmbedder import BaseEmbedder
from langchain.embeddings import OpenAIEmbeddings
import os
from typing import Optional

try:
    from chromadb.utils import embedding_functions
except RuntimeError:
    from embedchain.utils import use_pysqlite3

    use_pysqlite3()
    from chromadb.utils import embedding_functions

class OpenAiEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig]  = None):
        if config.deployment_name:
            embeddings = OpenAIEmbeddings(deployment=config.deployment_name)
            embedding_fn=BaseEmbedder._langchain_default_concept(embeddings)
            super().__init__(embedding_fn=embedding_fn)
        else:
            if os.getenv("OPENAI_API_KEY") is None and os.getenv("OPENAI_ORGANIZATION") is None:
                raise ValueError("OPENAI_API_KEY or OPENAI_ORGANIZATION environment variables not provided")  # noqa:E501
            embedding_fn=embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                organization_id=os.getenv("OPENAI_ORGANIZATION"),
                model_name=config.model,
            )
            super().__init__(embedding_fn=embedding_fn)
