import importlib
from typing import Dict, Optional, Union

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.configs.llms.azure import AzureOpenAIConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.deepseek import DeepSeekConfig
from mem0.configs.llms.lmstudio import LMStudioConfig
from mem0.configs.llms.ollama import OllamaConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.configs.llms.vllm import VllmConfig
from mem0.embeddings.mock import MockEmbeddings


def load_class(class_type):
    module_path, class_name = class_type.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class LlmFactory:
    """
    Factory for creating LLM instances with appropriate configurations.
    Supports both old-style BaseLlmConfig and new provider-specific configs.
    """

    # Provider mappings with their config classes
    provider_to_class = {
        "ollama": ("mem0.llms.ollama.OllamaLLM", OllamaConfig),
        "openai": ("mem0.llms.openai.OpenAILLM", OpenAIConfig),
        "groq": ("mem0.llms.groq.GroqLLM", BaseLlmConfig),
        "together": ("mem0.llms.together.TogetherLLM", BaseLlmConfig),
        "aws_bedrock": ("mem0.llms.aws_bedrock.AWSBedrockLLM", BaseLlmConfig),
        "litellm": ("mem0.llms.litellm.LiteLLM", BaseLlmConfig),
        "azure_openai": ("mem0.llms.azure_openai.AzureOpenAILLM", AzureOpenAIConfig),
        "openai_structured": ("mem0.llms.openai_structured.OpenAIStructuredLLM", OpenAIConfig),
        "anthropic": ("mem0.llms.anthropic.AnthropicLLM", AnthropicConfig),
        "azure_openai_structured": ("mem0.llms.azure_openai_structured.AzureOpenAIStructuredLLM", AzureOpenAIConfig),
        "gemini": ("mem0.llms.gemini.GeminiLLM", BaseLlmConfig),
        "deepseek": ("mem0.llms.deepseek.DeepSeekLLM", DeepSeekConfig),
        "xai": ("mem0.llms.xai.XAILLM", BaseLlmConfig),
        "sarvam": ("mem0.llms.sarvam.SarvamLLM", BaseLlmConfig),
        "lmstudio": ("mem0.llms.lmstudio.LMStudioLLM", LMStudioConfig),
        "vllm": ("mem0.llms.vllm.VllmLLM", VllmConfig),
        "langchain": ("mem0.llms.langchain.LangchainLLM", BaseLlmConfig),
    }

    @classmethod
    def create(cls, provider_name: str, config: Optional[Union[BaseLlmConfig, Dict]] = None, **kwargs):
        """
        Create an LLM instance with the appropriate configuration.

        Args:
            provider_name (str): The provider name (e.g., 'openai', 'anthropic')
            config: Configuration object or dict. If None, will create default config
            **kwargs: Additional configuration parameters

        Returns:
            Configured LLM instance

        Raises:
            ValueError: If provider is not supported
        """
        if provider_name not in cls.provider_to_class:
            raise ValueError(f"Unsupported Llm provider: {provider_name}")

        class_type, config_class = cls.provider_to_class[provider_name]
        llm_class = load_class(class_type)

        # Handle configuration
        if config is None:
            # Create default config with kwargs
            config = config_class(**kwargs)
        elif isinstance(config, dict):
            # Merge dict config with kwargs
            config.update(kwargs)
            config = config_class(**config)
        elif isinstance(config, BaseLlmConfig):
            # Convert base config to provider-specific config if needed
            if config_class != BaseLlmConfig:
                # Convert to provider-specific config
                config_dict = {
                    "model": config.model,
                    "temperature": config.temperature,
                    "api_key": config.api_key,
                    "max_tokens": config.max_tokens,
                    "top_p": config.top_p,
                    "top_k": config.top_k,
                    "enable_vision": config.enable_vision,
                    "vision_details": config.vision_details,
                    "http_client_proxies": config.http_client,
                }
                config_dict.update(kwargs)
                config = config_class(**config_dict)
            else:
                # Use base config as-is
                pass
        else:
            # Assume it's already the correct config type
            pass

        return llm_class(config)

    @classmethod
    def register_provider(cls, name: str, class_path: str, config_class=None):
        """
        Register a new provider.

        Args:
            name (str): Provider name
            class_path (str): Full path to LLM class
            config_class: Configuration class for the provider (defaults to BaseLlmConfig)
        """
        if config_class is None:
            config_class = BaseLlmConfig
        cls.provider_to_class[name] = (class_path, config_class)

    @classmethod
    def get_supported_providers(cls) -> list:
        """
        Get list of supported providers.

        Returns:
            list: List of supported provider names
        """
        return list(cls.provider_to_class.keys())


class EmbedderFactory:
    provider_to_class = {
        "openai": "mem0.embeddings.openai.OpenAIEmbedding",
        "ollama": "mem0.embeddings.ollama.OllamaEmbedding",
        "huggingface": "mem0.embeddings.huggingface.HuggingFaceEmbedding",
        "azure_openai": "mem0.embeddings.azure_openai.AzureOpenAIEmbedding",
        "gemini": "mem0.embeddings.gemini.GoogleGenAIEmbedding",
        "vertexai": "mem0.embeddings.vertexai.VertexAIEmbedding",
        "together": "mem0.embeddings.together.TogetherEmbedding",
        "lmstudio": "mem0.embeddings.lmstudio.LMStudioEmbedding",
        "langchain": "mem0.embeddings.langchain.LangchainEmbedding",
        "aws_bedrock": "mem0.embeddings.aws_bedrock.AWSBedrockEmbedding",
    }

    @classmethod
    def create(cls, provider_name, config, vector_config: Optional[dict]):
        if provider_name == "upstash_vector" and vector_config and vector_config.enable_embeddings:
            return MockEmbeddings()
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
            embedder_instance = load_class(class_type)
            base_config = BaseEmbedderConfig(**config)
            return embedder_instance(base_config)
        else:
            raise ValueError(f"Unsupported Embedder provider: {provider_name}")


class VectorStoreFactory:
    provider_to_class = {
        "qdrant": "mem0.vector_stores.qdrant.Qdrant",
        "chroma": "mem0.vector_stores.chroma.ChromaDB",
        "pgvector": "mem0.vector_stores.pgvector.PGVector",
        "milvus": "mem0.vector_stores.milvus.MilvusDB",
        "upstash_vector": "mem0.vector_stores.upstash_vector.UpstashVector",
        "azure_ai_search": "mem0.vector_stores.azure_ai_search.AzureAISearch",
        "pinecone": "mem0.vector_stores.pinecone.PineconeDB",
        "mongodb": "mem0.vector_stores.mongodb.MongoDB",
        "redis": "mem0.vector_stores.redis.RedisDB",
        "valkey": "mem0.vector_stores.valkey.ValkeyDB",
        "databricks": "mem0.vector_stores.databricks.Databricks",
        "elasticsearch": "mem0.vector_stores.elasticsearch.ElasticsearchDB",
        "vertex_ai_vector_search": "mem0.vector_stores.vertex_ai_vector_search.GoogleMatchingEngine",
        "opensearch": "mem0.vector_stores.opensearch.OpenSearchDB",
        "supabase": "mem0.vector_stores.supabase.Supabase",
        "weaviate": "mem0.vector_stores.weaviate.Weaviate",
        "faiss": "mem0.vector_stores.faiss.FAISS",
        "langchain": "mem0.vector_stores.langchain.Langchain",
        "s3_vectors": "mem0.vector_stores.s3_vectors.S3Vectors",
        "baidu": "mem0.vector_stores.baidu.BaiduDB",
        "neptune": "mem0.vector_stores.neptune_analytics.NeptuneAnalyticsVector",
    }

    @classmethod
    def create(cls, provider_name, config):
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
            if not isinstance(config, dict):
                config = config.model_dump()
            vector_store_instance = load_class(class_type)
            return vector_store_instance(**config)
        else:
            raise ValueError(f"Unsupported VectorStore provider: {provider_name}")

    @classmethod
    def reset(cls, instance):
        instance.reset()
        return instance


class GraphStoreFactory:
    """
    Factory for creating MemoryGraph instances for different graph store providers.
    Usage: GraphStoreFactory.create(provider_name, config)
    """

    provider_to_class = {
        "memgraph": "mem0.memory.memgraph_memory.MemoryGraph",
        "neptune": "mem0.graphs.neptune.neptunegraph.MemoryGraph",
        "neptunedb": "mem0.graphs.neptune.neptunedb.MemoryGraph",
        "kuzu": "mem0.memory.kuzu_memory.MemoryGraph",
        "default": "mem0.memory.graph_memory.MemoryGraph",
    }

    @classmethod
    def create(cls, provider_name, config):
        class_type = cls.provider_to_class.get(provider_name, cls.provider_to_class["default"])
        try:
            GraphClass = load_class(class_type)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Could not import MemoryGraph for provider '{provider_name}': {e}")
        return GraphClass(config)
