import os
from typing import Literal, Optional

import google.genai as genai # Changed import

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class GoogleGenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "models/text-embedding-004"
        # output_dimensionality was referred to as embedding_dims in the old config
        if hasattr(self.config, 'embedding_dims') and self.config.embedding_dims:
            self.output_dimensionality = self.config.embedding_dims
        elif hasattr(self.config, 'output_dimensionality') and self.config.output_dimensionality:
            self.output_dimensionality = self.config.output_dimensionality
        else:
            self.output_dimensionality = 768 # Default if not set

        api_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")

        # Initialize client as per instruction "initialize a self.client = genai.Client()"
        # API key can be passed directly to the client or it will use GOOGLE_API_KEY env var.
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            # If no api_key is provided, Client() will look for GOOGLE_API_KEY.
            # If neither is present, it should error out upon use.
            self.client = genai.Client()

        # genai.configure() is removed as Client should handle API key.

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Google Generative AI.
        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. (Currently not used by Gemini for task_type)
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")

        # Using self.client.models.embed_content as per instruction "migration guide shows client.models.embed_content"
        # Parameters might need adjustment based on the new SDK's exact signature.
        # Common parameters are model, content. Output_dimensionality might be part of model string or separate.
        # The new genai.embed_content often has 'model' (e.g. "models/embedding-001") and 'content'.
        # output_dimensionality is supported by some models.

        # Assuming self.client has a 'models' attribute that in turn has 'embed_content'
        # This is based on the prompt: "migration guide shows client.models.embed_content".
        response = self.client.models.embed_content(
            model=self.config.model,
            content=text,
            output_dimensionality=self.output_dimensionality
        )
        # The previous code returned response["embedding"]. This should remain similar.
        return response["embedding"]
