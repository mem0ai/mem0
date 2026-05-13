import os
from mem0 import Memory

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
            "api_key": "${deepseek-key}",
            "temperature": 0.1,
            "max_tokens": 2000,
            "deepseek_base_url": "https://api.deepseek.com"
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "Qwen/Qwen3-VL-Embedding-8B",
            "api_key": "${siliconflow-key}",
            "openai_base_url": "https://api.siliconflow.cn/v1",
            "embedding_dims": 1024
        }
    }
}
