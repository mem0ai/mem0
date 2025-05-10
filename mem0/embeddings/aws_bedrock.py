import json
from typing import Literal, Optional

try:
    import boto3
except ImportError:
    raise ImportError("The 'boto3' library is required. Please install it using 'pip install boto3'.")

import numpy as np

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class AWSBedrockEmbedding(EmbeddingBase):
    """AWS Bedrock embedding implementation.

    This class uses AWS Bedrock's embedding models.
    """

    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "amazon.titan-embed-text-v1"
        self.client = boto3.client("bedrock-runtime")

    def _normalize_vector(self, embeddings):
        """Normalize the embedding to a unit vector."""
        emb = np.array(embeddings)
        norm_emb = emb / np.linalg.norm(emb)
        return norm_emb.tolist()

    def _get_embedding(self, text):
        """Call out to Bedrock embedding endpoint."""

        # Format input body based on the provider
        provider = self.config.model.split(".")[0]
        input_body = {}

        if provider == "cohere":
            input_body["input_type"] = "search_document"
            input_body["texts"] = [text]
        else:
            # Amazon and other providers
            input_body["inputText"] = text

        body = json.dumps(input_body)

        try:
            response = self.client.invoke_model(
                body=body,
                modelId=self.config.model,
                accept="application/json",
                contentType="application/json",
            )

            response_body = json.loads(response.get("body").read())

            if provider == "cohere":
                embeddings = response_body.get("embeddings")[0]
            else:
                embeddings = response_body.get("embedding")

            return embeddings
        except Exception as e:
            raise ValueError(f"Error getting embedding from AWS Bedrock: {e}")

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using AWS Bedrock.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        return self._get_embedding(text)
