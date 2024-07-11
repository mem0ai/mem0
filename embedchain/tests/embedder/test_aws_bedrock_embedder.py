from unittest.mock import patch

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.aws_bedrock import AWSBedrockEmbedder


def test_aws_bedrock_embedder_with_model(monkeypatch):
    config = BaseEmbedderConfig(model="test-model", model_kwargs={"param": "value"})
    with patch("embedchain.embedder.aws_bedrock.BedrockEmbeddings") as mock_embeddings:
        embedder = AWSBedrockEmbedder(config=config)
        assert embedder.config.model == "test-model"
        assert embedder.config.model_kwargs == {"param": "value"}
        mock_embeddings.assert_called_once_with(model_id="test-model", model_kwargs={"param": "value"})
