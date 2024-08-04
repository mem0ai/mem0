
import openai
import os, time,sys
sys.path.append("../")
from mem0 import Memory
# We tested the scenario where embedding and LLM are provided by different interfaces from azure_openai. If an interface can provide both embedding and LLM simultaneously, then it is sufficient to set the three environment variables: “AZURE_OPENAI_API_KEY”, “AZURE_OPENAI_ENDPOINT”, and “OPENAI_API_VERSION”.
os.environ["AZURE_OPENAI_API_KEY"] = "702acd8694634c4abce4223479d0bcf8"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://yuaiweiwu-gpt4o.openai.azure.com/"
os.environ["OPENAI_API_VERSION"] = "2024-05-01-preview"

os.environ["EMBED_AZURE_OPENAI_API_KEY"] = "c70302f0120b4a99b54886a3b1e12610"
os.environ["EMBED_AZURE_OPENAI_ENDPOINT"] = "https://aitogether-japan.openai.azure.com/"
os.environ["EMBED_OPENAI_API_VERSION"] = "2023-08-01-preview"

config = {
    "llm": {
        "provider": "azure_openai",
        "config": {
            "model": "gpt-4o",
            "temperature": 0.1,
            "max_tokens": 2000,
        }
    },
    "embedder":{
        "provider":"azure_openai"
    }
    
}

m = Memory.from_config(config)
m.add("Likes to play cricket on weekends", user_id="alice", metadata={"category": "hobbies"})

related_memories = m.search(query="What are Alice's hobbies?", user_id="alice")
print(related_memories)
all_memories = m.get_all()
memory_id = all_memories[0]["id"] 
history = m.history(memory_id=memory_id)
print(history)