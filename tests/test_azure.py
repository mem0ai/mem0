
import openai
import os, time,sys
sys.path.append("../")
from mem0 import Memory
# We tested the scenario where embedding and LLM are provided by different interfaces from azure_openai. If an interface can provide both embedding and LLM simultaneously, then it is sufficient to set the three environment variables: “AZURE_OPENAI_API_KEY”, “AZURE_OPENAI_ENDPOINT”, and “OPENAI_API_VERSION”.
os.environ["AZURE_OPENAI_API_KEY"] = ""
os.environ["AZURE_OPENAI_ENDPOINT"] = ""
os.environ["OPENAI_API_VERSION"] = ""

os.environ["EMBED_AZURE_OPENAI_API_KEY"] = ""
os.environ["EMBED_AZURE_OPENAI_ENDPOINT"] = ""
os.environ["EMBED_OPENAI_API_VERSION"] = ""

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
        "provider":"litellm"
    }
    
}

m = Memory.from_config(config)
m.add("Likes to play cricket on weekends", user_id="alice", metadata={"category": "hobbies"})

related_memories = m.search(query="What are Alice's hobbies?", user_id="alice")
print(related_memories)
all_memories = m.get_all()
memory_id = all_memories[0]["id"] 
history = m.history(memory_id=memory_id)
