import os
import warnings
from typing import Literal, Optional, List

from openai import OpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class BaiLianEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or os.getenv("EMBEDDER_CONFIG_MODEL","text-embedding-v4")
        self.config.embedding_dims = self.config.embedding_dims or int(os.getenv("EMBEDDER_CONFIG_DIMS","1536"))

        api_key = (self.config.api_key
                   or os.getenv("DASHSCOPE_API_KEY")
                   or os.getenv("EMBEDDER_API_KEY"))
        base_url = (
            self.config.openai_base_url
            or os.getenv("DASHSCOPE_BASE_URL")
            or os.getenv("EMBEDDER_BASE_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using BaiLian.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        return (
            self.client.embeddings.create(input=[text], model=self.config.model, dimensions=self.config.embedding_dims, encoding_format = "float")
            .data[0]
            .embedding
        )
    
    def batch_embed(self, texts: List[str], memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Batch embed multiple texts for better performance.
        API limit: Maximum 10 texts per batch. Automatically splits into multiple batches if needed.
        
        Args:
            texts (List[str]): List of texts to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        
        Returns:
            List[list]: List of embedding vectors.
        """
        if not texts:
            return []
        
        # Clean texts
        cleaned_texts = [text.replace("\n", " ") for text in texts]
        
        # Batch size limit: 10 texts per API call
        batch_size = 10
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(cleaned_texts), batch_size):
            batch = cleaned_texts[i:i + batch_size]
            
            # Batch API call
            response = self.client.embeddings.create(
                input=batch,
                model=self.config.model,
                dimensions=self.config.embedding_dims,
                encoding_format="float"
            )
            
            # Collect embeddings from this batch
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
