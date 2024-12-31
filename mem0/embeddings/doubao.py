import os
from typing import Optional


try:
    from volcenginesdkarkruntime import Ark
except ImportError:
    raise ImportError("The 'volcenginesdkarkruntime' library is required. Please install it using 'pip install volcenginesdkarkruntime'.")


from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase



class DouBaoEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model 
        self.config.embedding_dims = self.config.embedding_dims or 2048

        api_key = self.config.api_key or os.getenv("ARK_API_KEY")
        base_url = "https://ark.cn-beijing.volces.com/api/v3"
        self.client = Ark(api_key=api_key, base_url=base_url)

    def embed(self, text):
        """
        Get the embedding for the given text using DouBao.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        return self.client.embeddings.create(input=[text], model=self.config.model).data[0].embedding
