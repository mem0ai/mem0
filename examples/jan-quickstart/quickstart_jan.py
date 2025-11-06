import os
from mem0 import Memory

config = {
    "llm": {
        "provider": "jan",
        "config": {
            "model": "openai_gpt-oss-20b-IQ2_M",
            "api_key": "JanServer",
            "jan_base_url": "http://localhost:1337/v1/",
            "temperature": 0.2,
            "max_tokens": 2000
        }
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
 #           "model": "multi-qa-MiniLM-L6-cos-v1"
            "model": "sangmini/msmarco-cotmae-MiniLM-L12_en-ko-ja"
        }
    }
}

m = Memory.from_config(config)

# For a user
messages = [
    {
        "role": "user",
        "content": "I like to drink coffee in the morning and go for a walk"
    }
]
result = m.add(messages, user_id="alice", metadata={"category": "preferences"})

related_memories = m.search("Should I drink coffee or tea?", user_id="alice")

print(related_memories)