from litellm import embedding

from mem0.embeddings.base import EmbeddingBase


class LiteLLMEmbedding(EmbeddingBase):
    def __init__(self, model="text-embedding-ada-002"):
        self.model = model
        self.dims = 1536

    def embed(self, text):
        """
        Get the embedding for the given text using LiteLLM.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        response = embedding(model=self.model, input=[text])
