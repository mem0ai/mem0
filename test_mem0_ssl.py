import os
from mem0 import Memory

config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "api_key": os.environ["OPENAI_API_KEY"],
            "ssl_verify": False
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
            "api_key": os.environ["OPENAI_API_KEY"],
            "ssl_verify": False
        }
    }
}

m = Memory.from_config(config)
response = m.chat("Hello! Can you respond?")
print(response)
