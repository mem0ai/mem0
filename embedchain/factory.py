import importlib


def load_class(class_type):
    module_path, class_name = class_type.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class LlmFactory:
    provider_to_config_class = {
        "openai": "embedchain.config.llm.base_llm_config.BaseLlmConfig",
    }
    provider_to_class = {
        "openai": "embedchain.llm.openai.OpenAILlm",
    }

    @classmethod
    def create(cls, provider_name, config_data):
        class_type = cls.provider_to_class.get(provider_name)
        config_class_type = cls.provider_to_config_class.get(provider_name)
        if class_type:
            llm_class = load_class(class_type)
            llm_config_class = load_class(config_class_type)
            return llm_class(config=llm_config_class(**config_data))
        else:
            raise ValueError(f"Unsupported Llm provider: {provider_name}")


class EmbedderFactory:
    provider_to_class = {
        "openai": "embedchain.embedder.openai.OpenAIEmbedder",
    }
    provider_to_config_class = {
        "openai": "embedchain.config.embedder.base.BaseEmbedderConfig",
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


class VectorDBFactory:
    provider_to_class = {
        "chroma": "embedchain.vectordb.chroma.ChromaDB",
        "opensearch": "embedchain.vectordb.opensearch.OpenSearchDB",
    }
    provider_to_config_class = {
        "opensearch": "embedchain.config.vectordb.opensearch.OpenSearchDBConfig",
        "chroma": "embedchain.config.vectordb.chroma.ChromaDbConfig",
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
