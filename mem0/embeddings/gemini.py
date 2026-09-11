import os
from typing import Literal, Optional
from google import genai
from google.genai import types
from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

class GoogleGenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)
        # Default to text-embedding-004
        self.config.model = self.config.model or "text-embedding-004"
        self.config.embedding_dims = (
            self.config.embedding_dims 
            or getattr(self.config, "output_dimensionality", None) 
            or 768
        )
        api_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)

    def _get_task_type(self, memory_action: Optional[str]) -> Optional[str]:
        """Maps mem0 memory actions to Google GenAI TaskTypes."""
        mapping = {
            "search": "RETRIEVAL_QUERY",
            "add": "RETRIEVAL_DOCUMENT",
            "update": "RETRIEVAL_DOCUMENT",
        }
        return mapping.get(memory_action)

    def embed(self, text: str, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Google Generative AI.
        """
        text = text.replace("\n", " ")
        task_type = self._get_task_type(memory_action)
        
        config = types.EmbedContentConfig(
            output_dimensionality=self.config.embedding_dims,
            task_type=task_type
        )
        
        response = self.client.models.embed_content(
            model=self.config.model, 
            contents=text, 
            config=config
        )
        return response.embeddings[0].values

    def embed_batch(self, texts: list[str], memory_action: Optional[Literal["add", "search", "update"]] = "add"):
        if not texts:
            return []
            
        task_type = self._get_task_type(memory_action)
        config = types.EmbedContentConfig(
            output_dimensionality=self.config.embedding_dims,
            task_type=task_type
        )
        
        MAX_BATCH = 100
        all_embeddings = []
        for i in range(0, len(texts), MAX_BATCH):
            chunk = [t.replace("\n", " ") for t in texts[i : i + MAX_BATCH]]
            response = self.client.models.embed_content(
                model=self.config.model, 
                contents=chunk, 
                config=config
            )
            all_embeddings.extend([e.values for e in response.embeddings])
            
        if len(all_embeddings) != len(texts):
            raise ValueError(
                f"Gemini embed_batch() returned {len(all_embeddings)} embeddings for {len(texts)} texts "
                f"using model '{self.config.model}'"
            )
        return all_embeddings
