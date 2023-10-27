import importlib


def load_class(class_type):
    module_path, class_name = class_type.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class LlmFactory:
    provider_to_class = {
        "anthropic": "embedchain.llm.anthropic.AnthropicLlm",
        "azure_openai": "embedchain.llm.azure_openai.AzureOpenAILlm",
        "cohere": "embedchain.llm.cohere.CohereLlm",
        "gpt4all": "embedchain.llm.gpt4all.GPT4ALLLlm",
        "huggingface": "embedchain.llm.huggingface.HuggingFaceLlm",
        "jina": "embedchain.llm.jina.JinaLlm",
        "llama2": "embedchain.llm.llama2.Llama2Llm",
        "openai": "embedchain.llm.openai.OpenAILlm",
        "vertexai": "embedchain.llm.vertex_ai.VertexAILlm",
    }
    provider_to_config_class = {
        "embedchain": "embedchain.config.llm.base.BaseLlmConfig",
        "openai": "embedchain.config.llm.base.BaseLlmConfig",
        "anthropic": "embedchain.config.llm.base.BaseLlmConfig",
    }

    @classmethod
    def create(cls, provider_name, config_data):
        class_type = cls.provider_to_class.get(provider_name)
        # Default to embedchain base config if the provider is not in the config map
        config_name = "embedchain" if provider_name not in cls.provider_to_config_class else provider_name
        config_class_type = cls.provider_to_config_class.get(config_name)
        if class_type:
            llm_class = load_class(class_type)
            llm_config_class = load_class(config_class_type)
            return llm_class(config=llm_config_class(**config_data))
        else:
            raise ValueError(f"Unsupported Llm provider: {provider_name}")


class EmbedderFactory:
    provider_to_class = {
        "azure_openai": "embedchain.embedder.openai.OpenAIEmbedder",
        "gpt4all": "embedchain.embedder.gpt4all.GPT4AllEmbedder",
        "huggingface": "embedchain.embedder.huggingface.HuggingFaceEmbedder",
        "openai": "embedchain.embedder.openai.OpenAIEmbedder",
        "vertexai": "embedchain.embedder.vertexai.VertexAIEmbedder",
    }
    provider_to_config_class = {
        "azure_openai": "embedchain.config.embedder.base.BaseEmbedderConfig",
        "openai": "embedchain.config.embedder.base.BaseEmbedderConfig",
        "gpt4all": "embedchain.config.embedder.base.BaseEmbedderConfig",
    }

    @classmethod
    def create(cls, provider_name, config_data):
        class_type = cls.provider_to_class.get(provider_name)
        # Default to openai config if the provider is not in the config map
        config_name = "openai" if provider_name not in cls.provider_to_config_class else provider_name
        config_class_type = cls.provider_to_config_class.get(config_name)
        if class_type:
            embedder_class = load_class(class_type)
            embedder_config_class = load_class(config_class_type)
            return embedder_class(config=embedder_config_class(**config_data))
        else:
            raise ValueError(f"Unsupported Embedder provider: {provider_name}")


class VectorDBFactory:
    provider_to_class = {
        "chroma": "embedchain.vector_db.chroma.ChromaDB",
        "elasticsearch": "embedchain.vector_db.elasticsearch.ElasticsearchDB",
        "opensearch": "embedchain.vector_db.opensearch.OpenSearchDB",
        "pinecone": "embedchain.vector_db.pinecone.PineconeDB",
        "qdrant": "embedchain.vector_db.qdrant.QdrantDB",
        "weaviate": "embedchain.vector_db.weaviate.WeaviateDB",
        "zilliz": "embedchain.vector_db.zilliz.ZillizVectorDB",
    }
    provider_to_config_class = {
        "chroma": "embedchain.config.vector_db.chroma.ChromaDbConfig",
        "elasticsearch": "embedchain.config.vector_db.elasticsearch.ElasticsearchDBConfig",
        "opensearch": "embedchain.config.vector_db.opensearch.OpenSearchDBConfig",
        "pinecone": "embedchain.config.vector_db.pinecone.PineconeDBConfig",
        "qdrant": "embedchain.config.vector_db.qdrant.QdrantDBConfig",
        "weaviate": "embedchain.config.vector_db.weaviate.WeaviateDBConfig",
        "zilliz": "embedchain.config.vector_db.zilliz.ZillizDBConfig",
    }

    @classmethod
    def create(cls, provider_name, config_data):
        class_type = cls.provider_to_class.get(provider_name)
        config_class_type = cls.provider_to_config_class.get(provider_name)
        if class_type:
            embedder_class = load_class(class_type)
            embedder_config_class = load_class(config_class_type)
            return embedder_class(config=embedder_config_class(**config_data))
        else:
            raise ValueError(f"Unsupported Embedder provider: {provider_name}")
