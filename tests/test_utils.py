import yaml

from embedchain.utils.misc import validate_config

CONFIG_YAMLS = [
    "configs/anthropic.yaml",
    "configs/azure_openai.yaml",
    "configs/chroma.yaml",
    "configs/chunker.yaml",
    "configs/cohere.yaml",
    "configs/together.yaml",
    "configs/ollama.yaml",
    "configs/full-stack.yaml",
    "configs/gpt4.yaml",
    "configs/gpt4all.yaml",
    "configs/huggingface.yaml",
    "configs/jina.yaml",
    "configs/llama2.yaml",
    "configs/opensearch.yaml",
    "configs/opensource.yaml",
    "configs/pinecone.yaml",
    "configs/vertexai.yaml",
    "configs/weaviate.yaml",
]


def test_all_config_yamls():
    """Test that all config yamls are valid."""
    for config_yaml in CONFIG_YAMLS:
        with open(config_yaml, "r") as f:
            config = yaml.safe_load(f)
        assert config is not None

        try:
            validate_config(config)
        except Exception as e:
            print(f"Error in {config_yaml}: {e}")
            raise e
