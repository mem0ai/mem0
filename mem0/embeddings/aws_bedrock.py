import io
import json
import os
import time
from typing import Literal, Optional
from urllib.parse import quote

try:
    import boto3
except ImportError:
    raise ImportError("The 'boto3' library is required. Please install it using 'pip install boto3'.")

import numpy as np
import requests as _requests

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class _EmbeddingBearerTokenProvider:
    """Generates and caches short-term Bedrock bearer tokens for embedding client."""

    def __init__(self, region: str):
        self._region = region
        self._token: Optional[str] = None
        self._expires_at: float = 0

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at:
            return self._token
        from aws_bedrock_token_generator import provide_token
        self._token = provide_token(region=self._region)
        self._expires_at = time.time() + 11 * 3600
        return self._token


class _EmbeddingBearerClient:
    """Bearer token client for bedrock-runtime invoke_model (embeddings)."""

    def __init__(self, region: str):
        self._region = region
        self._base_url = f"https://bedrock-runtime.{region}.amazonaws.com"
        self._token_provider = _EmbeddingBearerTokenProvider(region)

    def invoke_model(self, **kwargs):
        model_id = kwargs.get("modelId")
        body = kwargs.get("body")
        token = self._token_provider.get_token()
        url = f"{self._base_url}/model/{quote(model_id, safe='')}/invoke"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        resp = _requests.post(url, headers=headers, data=body)
        resp.raise_for_status()
        return {"body": io.BytesIO(resp.content)}


class AWSBedrockEmbedding(EmbeddingBase):
    """AWS Bedrock embedding implementation.

    This class uses AWS Bedrock's embedding models.
    """

    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "amazon.titan-embed-text-v1"

        aws_region = self.config.aws_region or "us-west-2"
        auth_mode = getattr(self.config, "auth_mode", "sigv4")

        if auth_mode == "api_key":
            self.client = _EmbeddingBearerClient(region=aws_region)
        else:
            aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
            aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
            aws_session_token = os.environ.get("AWS_SESSION_TOKEN", "")

            if hasattr(self.config, "aws_access_key_id"):
                aws_access_key = self.config.aws_access_key_id
            if hasattr(self.config, "aws_secret_access_key"):
                aws_secret_key = self.config.aws_secret_access_key

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
