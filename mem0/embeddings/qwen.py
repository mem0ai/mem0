import os

import dashscope

from mem0.embeddings.base import EmbeddingBase


class QwenEmbedding(EmbeddingBase):
    def __init__(self, model="text-embedding-v2"):
        self.model = model
        self.dims = 1536

    def embed(self, text):
        """
        Get the embedding for the given text using Tongyi Qwen.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")

        resp = dashscope.TextEmbedding.call(
            model=dashscope.TextEmbedding.Models.text_embedding_v1,
            api_key=os.getenv('DASHSCOPE_API_KEY'),  # 如果您没有配置环境变量，请将您的APIKEY填写在这里
            input=text)

        return resp["output"]["embeddings"][0]["embedding"]
