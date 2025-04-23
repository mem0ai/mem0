import logging
from mem0.configs.base import MemoryConfig
from mem0.configs.vector_stores.faiss import FAISSConfig
from mem0.configs.vector_stores.langchain import LangchainConfig
from mem0.embeddings.configs import EmbedderConfig
from mem0.llms.configs import LlmConfig
from mem0.memory.main import Memory
from mem0.vector_stores.configs import VectorStoreConfig
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Pass the initialized vector store to the config
config = {
    "llm": {
        "provider": "gemini"
    },
    "embedder": {
        "provider": "gemini"
    },
    "vector_store": {
        "provider": "milvus",
        "config": {
            "collection_name": "test",
            "embedding_model_dims": "768",
            # "url": "127.0.0.1",
            # "token": "8e4b8ca8cf2c67",
        }
    }
}

memory = Memory.from_config(config)

messages = [
    {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
    {"role": "assistant", "content": "How about a thriller movies? They can be quite engaging."},
    {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
    {"role": "assistant", "content": "Got it! I'll avoid thriller recommendations and suggest sci-fi movies in the future."}
]

# Store raw messages without inference
print("Adding memories...")
result = memory.add(messages, user_id="alice", metadata={"category": "movie_recommendations"}, infer=False)

# Get all memories
all_memories = memory.get_all(user_id="alice")
print(f"Found {len(all_memories['results'])} memories")

for m in all_memories['results']:
    print('=====')
    print('Memory ID:',m['id'])
    print('Memory:',m['memory'])
    print('Category:',m['metadata']['category'])
    print('User ID:',m['user_id'])
    print('=====')

print('\n\n\n')

print("\nStarting memory reset...")
try:
    memory.reset()
    print("Memory reset completed successfully!")
except Exception as e:
    print(f"Error during memory reset: {e}")

print("Test completed.")

print('=========================================================================================')

print(memory.history(all_memories['results'][0]['id']))

messages = [
    {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
    {"role": "assistant", "content": "How about a thriller movies? They can be quite engaging."},
    {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
    {"role": "assistant", "content": "Got it! I'll avoid thriller recommendations and suggest sci-fi movies in the future."}
]

# Store raw messages without inference
print("Adding memories...")
result = memory.add(messages, user_id="alice", metadata={"category": "movie_recommendations"}, infer=False)


all_memories1 = memory.get_all(user_id="alice")
print(f"Found {len(all_memories1['results'])} memories")

for m in all_memories1['results']:
    print('=====')
    print('Memory ID:',m['id'])
    print('Memory:',m['memory'])
    print('Category:',m['metadata']['category'])
    print('User ID:',m['user_id'])
    print('=====')

print('\n\n\n')