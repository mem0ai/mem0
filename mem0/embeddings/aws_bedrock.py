import json
import os
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

        # Get AWS config from environment variables or use defaults
        aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        aws_session_token = os.environ.get("AWS_SESSION_TOKEN", "")

        # Check if AWS config is provided in the config
        if hasattr(self.config, "aws_access_key_id"):
            aws_access_key = self.config.aws_access_key_id
        if hasattr(self.config, "aws_secret_access_key"):
            aws_secret_key = self.config.aws_secret_access_key
        # Honor a session token supplied via config (temporary credentials from
        # STS / assume-role), falling back to the env var when unset. The LLM
        # Bedrock provider already supports this; mirror it here.
        if getattr(self.config, "aws_session_token", None):
            aws_session_token = self.config.aws_session_token

        # AWS region is always set in config - see BaseEmbedderConfig
        aws_region = self.config.aws_region or "us-west-2"

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=aws_access_key if aws_access_key else None,
            aws_secret_access_key=aws_secret_key if aws_secret_key else None,
            aws_session_token=aws_session_token if aws_session_token else None,
        )

    def _normalize_vector(self, embeddings):
        """Normalize the embedding to a unit vector."""
        emb = np.array(embeddings)
        norm_emb = emb / np.linalg.norm(emb)
        return norm_emb.tolist()

    # Cohere v3 embeddings are asymmetric: queries and documents must be encoded
    # with different ``input_type`` values, otherwise retrieval quality degrades.
    # mem0 signals the context via ``memory_action`` ("add"/"update"/"search").
    _COHERE_INPUT_TYPES = {
        "add": "search_document",
        "update": "search_document",
        "search": "search_query",
    }
    _DEFAULT_COHERE_INPUT_TYPE = "search_document"

    def _get_embedding(self, text, memory_action: Optional[str] = None):
        """Call out to Bedrock embedding endpoint."""

        # Format input body based on the provider
        provider = self.config.model.split(".")[0]
        input_body = {}

        if provider == "cohere":
            input_body["input_type"] = self._COHERE_INPUT_TYPES.get(memory_action, self._DEFAULT_COHERE_INPUT_TYPE)
            input_body["texts"] = [text]
        else:
            # Amazon and other providers
            input_body["inputText"] = text
            # Titan Text Embeddings V2 accepts an optional output dimension
            # (256/512/1024). Only forward embedding_dims when the user set it,
            # mirroring the OpenAI embedder's guarded `dimensions` pass-through.
            if self.config.embedding_dims is not None and "v2" in self.config.model:
                input_body["dimensions"] = self.config.embedding_dims

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
        return self._get_embedding(text, memory_action)
