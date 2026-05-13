import os
import re
from mem0 import Memory

def load_config_with_env_vars(config_dict):
    """Recursively replace ${ENV_VAR} placeholders with actual environment variables."""
    if isinstance(config_dict, dict):
        return {key: load_config_with_env_vars(value) for key, value in config_dict.items()}
    elif isinstance(config_dict, list):
        return [load_config_with_env_vars(item) for item in config_dict]
    elif isinstance(config_dict, str):
        # Replace ${VAR_NAME} with os.getenv('VAR_NAME', default='')
        def replace_env_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, f"${{{var_name}}}")  # fallback to placeholder if not found
        return re.sub(r'\$\{([^}]+)\}', replace_env_var, config_dict)
    else:
        return config_dict

config = {
     "vector_store": {
        "provider": "pgvector",
        "config": {
            "host": "postgres",
            "port": 5432,
            "dbname": "mem0_app",
            "user": "postgres",
            "password": "postgres",
            "collection_name": "memories",
            "embedding_model_dims": 1024,
            "hnsw": True
        }
    },
    "llm": {
        "provider": "deepseek",
        "config": {
            "model": "deepseek-v4-flash",
            "api_key": "${DEEPSEEK_KEY}",
            "temperature": 0.1,
            "max_tokens": 2000,
            "deepseek_base_url": "https://api.deepseek.com"
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "Qwen/Qwen3-VL-Embedding-8B",
            "api_key": "${SILICONFLOW_KEY}",
            "openai_base_url": "https://api.siliconflow.cn/v1",
            "embedding_dims": 1024
        }
    }
}

# Load config with environment variables resolved
config = load_config_with_env_vars(config)
