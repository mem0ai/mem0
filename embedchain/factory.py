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
        "together": "embedchain.llm.together.TogetherLlm",
        "gpt4all": "embedchain.llm.gpt4all.GPT4ALLLlm",
        "ollama": "embedchain.llm.ollama.OllamaLlm",
        "huggingface": "embedchain.llm.huggingface.HuggingFaceLlm",
        "jina": "embedchain.llm.jina.JinaLlm",
        "llama2": "embedchain.llm.llama2.Llama2Llm",
        "openai": "embedchain.llm.openai.OpenAILlm",
        "vertexai": "embedchain.llm.vertex_ai.VertexAILlm",
        "google": "embedchain.llm.google.GoogleLlm",
        "aws_bedrock": "embedchain.llm.aws_bedrock.AWSBedrockLlm",
        "mistralai": "embedchain.llm.mistralai.MistralAILlm",
        "clarifai": "embedchain.llm.clarifai.ClarifaiLlm",
        "groq": "embedchain.llm.groq.GroqLlm",
        "nvidia": "embedchain.llm.nvidia.NvidiaLlm",
        "vllm": "embedchain.llm.vllm.VLLM",
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
        "google": "embedchain.embedder.google.GoogleAIEmbedder",
        "mistralai": "embedchain.embedder.mistralai.MistralAIEmbedder",
        "clarifai": "embedchain.embedder.clarifai.ClarifaiEmbedder",
        "nvidia": "embedchain.embedder.nvidia.NvidiaEmbedder",
        "cohere": "embedchain.embedder.cohere.CohereEmbedder",
        "ollama": "embedchain.embedder.ollama.OllamaEmbedder",
    }
    provider_to_config_class = {
        "azure_openai": "embedchain.config.embedder.base.BaseEmbedderConfig",
        "google": "embedchain.config.embedder.google.GoogleAIEmbedderConfig",
        "gpt4all": "embedchain.config.embedder.base.BaseEmbedderConfig",
        "huggingface": "embedchain.config.embedder.base.BaseEmbedderConfig",
        "clarifai": "embedchain.config.embedder.base.BaseEmbedderConfig",
        "openai": "embedchain.config.embedder.base.BaseEmbedderConfig",
        "ollama": "embedchain.config.embedder.ollama.OllamaEmbedderConfig",
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
        "chroma": "embedchain.vectordb.chroma.ChromaDB",
        "elasticsearch": "embedchain.vectordb.elasticsearch.ElasticsearchDB",
        "opensearch": "embedchain.vectordb.opensearch.OpenSearchDB",
        "lancedb": "embedchain.vectordb.lancedb.LanceDB",
        "pinecone": "embedchain.vectordb.pinecone.PineconeDB",
        "qdrant": "embedchain.vectordb.qdrant.QdrantDB",
        "weaviate": "embedchain.vectordb.weaviate.WeaviateDB",
        "zilliz": "embedchain.vectordb.zilliz.ZillizVectorDB",
    }
    provider_to_config_class = {
        "chroma": "embedchain.config.vectordb.chroma.ChromaDbConfig",
        "elasticsearch": "embedchain.config.vectordb.elasticsearch.ElasticsearchDBConfig",
        "opensearch": "embedchain.config.vectordb.opensearch.OpenSearchDBConfig",
        "lancedb": "embedchain.config.vectordb.lancedb.LanceDBConfig",
        "pinecone": "embedchain.config.vectordb.pinecone.PineconeDBConfig",
        "qdrant": "embedchain.config.vectordb.qdrant.QdrantDBConfig",
        "weaviate": "embedchain.config.vectordb.weaviate.WeaviateDBConfig",
        "zilliz": "embedchain.config.vectordb.zilliz.ZillizDBConfig",
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
