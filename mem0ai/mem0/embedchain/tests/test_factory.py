import os

import pytest

import embedchain
import embedchain.embedder.gpt4all
import embedchain.embedder.huggingface
import embedchain.embedder.openai
import embedchain.embedder.vertexai
import embedchain.llm.anthropic
import embedchain.llm.openai
import embedchain.vectordb.chroma
import embedchain.vectordb.elasticsearch
import embedchain.vectordb.opensearch
from embedchain.factory import EmbedderFactory, LlmFactory, VectorDBFactory


class TestFactories:
    @pytest.mark.parametrize(
        "provider_name, config_data, expected_class",
        [
            ("openai", {}, embedchain.llm.openai.OpenAILlm),
            ("anthropic", {}, embedchain.llm.anthropic.AnthropicLlm),
        ],
    )
    def test_llm_factory_create(self, provider_name, config_data, expected_class):
        os.environ["ANTHROPIC_API_KEY"] = "test_api_key"
        os.environ["OPENAI_API_KEY"] = "test_api_key"
        os.environ["OPENAI_API_BASE"] = "test_api_base"
        llm_instance = LlmFactory.create(provider_name, config_data)
        assert isinstance(llm_instance, expected_class)

    @pytest.mark.parametrize(
        "provider_name, config_data, expected_class",
        [
            ("gpt4all", {}, embedchain.embedder.gpt4all.GPT4AllEmbedder),
            (
                "huggingface",
                {"model": "sentence-transformers/all-mpnet-base-v2", "vector_dimension": 768},
                embedchain.embedder.huggingface.HuggingFaceEmbedder,
            ),
            ("vertexai", {"model": "textembedding-gecko"}, embedchain.embedder.vertexai.VertexAIEmbedder),
            ("openai", {}, embedchain.embedder.openai.OpenAIEmbedder),
        ],
    )
    def test_embedder_factory_create(self, mocker, provider_name, config_data, expected_class):
        mocker.patch("embedchain.embedder.vertexai.VertexAIEmbedder", autospec=True)
        embedder_instance = EmbedderFactory.create(provider_name, config_data)
        assert isinstance(embedder_instance, expected_class)

    @pytest.mark.parametrize(
        "provider_name, config_data, expected_class",
        [
            ("chroma", {}, embedchain.vectordb.chroma.ChromaDB),
            (
                "opensearch",
                {"opensearch_url": "http://localhost:9200", "http_auth": ("admin", "admin")},
                embedchain.vectordb.opensearch.OpenSearchDB,
            ),
            ("elasticsearch", {"es_url": "http://localhost:9200"}, embedchain.vectordb.elasticsearch.ElasticsearchDB),
        ],
    )
    def test_vectordb_factory_create(self, mocker, provider_name, config_data, expected_class):
        mocker.patch("embedchain.vectordb.opensearch.OpenSearchDB", autospec=True)
        vectordb_instance = VectorDBFactory.create(provider_name, config_data)
        assert isinstance(vectordb_instance, expected_class)
