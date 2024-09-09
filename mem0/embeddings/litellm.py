import os
from typing import Optional

from litellm import embedding as litellm_embedding

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

class LiteLLM(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "vertex_ai/textembedding-gecko"

        credentials_path = self.config.vertex_credentials_json

        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        elif not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError(
                "Google application credentials JSON is not provided. Please provide a valid JSON path or set the 'GOOGLE_APPLICATION_CREDENTIALS' environment variable."
            )


    def embed(self, text):
        """
        Get the embedding for the given text using LiteLLM from Vertex AI.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        response = litellm_embedding(
            model=self.config.model,
            input=[text]
        )
        
        return response['data'][0]['embedding']
       

