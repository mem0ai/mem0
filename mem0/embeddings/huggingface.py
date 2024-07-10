from embedding.base import EmbeddingBase
from sentence_transformers import SentenceTransformer


class HuggingFaceEmbedding(EmbeddingBase):
    def __init__(self, model_name="multi-qa-MiniLM-L6-cos-v1"):
        self.model = SentenceTransformer(model_name)

    def get_embedding(self, text):
        """
        Get the embedding for the given text using Hugging Face.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        return self.model.encode(text)
