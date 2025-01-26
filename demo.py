from mem0 import Memory
import os
# Get Embedding Function
import openai
from typing import List
def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    text = text.replace("\n", " ")
    try:
        return openai.OpenAI().embeddings.create(input=[text], model=model).data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise

os.environ["OPENAI_API_KEY"] = "sk-"
config = {
    "vector_store": {
        "provider": "mongodb",
        "config": {
            "mdb_uri": "mongodb://0.0.0.0/?directConnection=true",
            "dbname": "DEMO",
            "collection_name": "TEST",
            "get_embedding": get_embedding,
            "embedding_model_dims": len(get_embedding("0")),
        }
    }
}
m = Memory.from_config(config)
result = m.add("I am working on improving my tennis skills. Suggest some online courses.", user_id="alice", metadata={"category": "hobbies"})
print(result)
result = m.add("I am learning how to code. Suggest some tutorials.", user_id="alice", metadata={"category": "hobbies"})
print(result)

related_memories = m.search(query="tennis", user_id="alice")
print(related_memories)

"""
Provider: qdrant
Available providers: ['mongodb', 'qdrant', 'chroma', 'pgvector', 'milvus', 'azure_ai_search', 'redis', 'elasticsearch']
Provider: mongodb
Available providers: ['mongodb', 'qdrant', 'chroma', 'pgvector', 'milvus', 'azure_ai_search', 'redis', 'elasticsearch']
INFO:mdb_toolkit.core:Importing core module
INFO:mdb_toolkit.core:Index 'BOOM_vector_index' does not exist in collection 'BOOM'.
db name BAB
collection name BOOM
index name BOOM_vector_index
INFO:mdb_toolkit.core:Collection 'BOOM' does not exist. Creating it now.
INFO:mdb_toolkit.core:Collection 'BOOM' created successfully.
INFO:mdb_toolkit.core:Index 'BOOM_vector_index' does not exist in collection 'BOOM'.
INFO:mdb_toolkit.core:Creating search index 'BOOM_vector_index' for collection 'BOOM'.
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/embeddings "HTTP/1.1 200 OK"
INFO:mdb_toolkit.core:Search index 'BOOM_vector_index' created successfully for collection 'BOOM'.
INFO:mem0.vector_stores.mongodb:Search index 'BOOM_vector_index' created successfully on 'BAB.BOOM'.
INFO:mem0.vector_stores.mongodb:Waiting for the search index to be READY...
INFO:mdb_toolkit.core:Index 'BOOM_vector_index' status: BUILDING
INFO:mdb_toolkit.core:Attempt 1: Search index 'BOOM_vector_index' not READY yet. Waiting 5 second(s)...
INFO:mdb_toolkit.core:Search index 'BOOM_vector_index' is READY.
INFO:mem0.vector_stores.mongodb:Search index 'BOOM_vector_index' is now READY and available!
Index is ready!
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/embeddings "HTTP/1.1 200 OK"
INFO:mem0.vector_stores.mongodb:Vector search completed. Found 0 documents.
INFO:mem0.vector_stores.mongodb:Search results: []
Existing Memories:  []
INFO:root:Total existing memories: 0
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO:root:{'id': '0', 'text': 'Working on improving tennis skills', 'event': 'ADD'}
INFO:root:Creating memory with data='Working on improving tennis skills'
INFO:mem0.vector_stores.mongodb:Inserting 1 vectors into collection 'BOOM'.
INFO:mem0.vector_stores.mongodb:Inserted 1 documents into 'BOOM'.
/Users/fabianvalle/dev/OPENSOURCE/mem0/demo.py:28: DeprecationWarning: The current add API output format is deprecated. To use the latest format, set `api_version='v1.1'`. The current format will be removed in mem0ai 1.1.0 and later versions.
  result = m.add("I am working on improving my tennis skills. Suggest some online courses.", user_id="alice", metadata={"category": "hobbies"})
[{'id': '77d4c3ff-db16-4605-9165-953ea52ca959', 'memory': 'Working on improving tennis skills', 'event': 'ADD'}]
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/embeddings "HTTP/1.1 200 OK"
INFO:mem0.vector_stores.mongodb:Vector search completed. Found 1 documents.
INFO:mem0.vector_stores.mongodb:Search results: [{'_id': '77d4c3ff-db16-4605-9165-953ea52ca959', 'id': '77d4c3ff-db16-4605-9165-953ea52ca959', 'payload': {'category': 'hobbies', 'user_id': 'alice', 'data': 'Working on improving tennis skills', 'hash': '4c3bc9f87b78418f19df6407bc86e006', 'created_at': '2025-01-25T15:59:26.421905-08:00'}, 'score': 0.673403263092041}]
Existing Memories:  [OutputData(id='77d4c3ff-db16-4605-9165-953ea52ca959', score=0.673403263092041, payload={'category': 'hobbies', 'user_id': 'alice', 'data': 'Working on improving tennis skills', 'hash': '4c3bc9f87b78418f19df6407bc86e006', 'created_at': '2025-01-25T15:59:26.421905-08:00'})]
Existing Memory:  id='77d4c3ff-db16-4605-9165-953ea52ca959' score=0.673403263092041 payload={'category': 'hobbies', 'user_id': 'alice', 'data': 'Working on improving tennis skills', 'hash': '4c3bc9f87b78418f19df6407bc86e006', 'created_at': '2025-01-25T15:59:26.421905-08:00'}
INFO:root:Total existing memories: 1
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO:root:{'id': '0', 'text': 'Working on improving tennis skills', 'event': 'NONE'}
INFO:root:NOOP for Memory.
INFO:root:{'id': '1', 'text': 'Learning how to code', 'event': 'ADD'}
INFO:root:Creating memory with data='Learning how to code'
INFO:mem0.vector_stores.mongodb:Inserting 1 vectors into collection 'BOOM'.
INFO:mem0.vector_stores.mongodb:Inserted 1 documents into 'BOOM'.
/Users/fabianvalle/dev/OPENSOURCE/mem0/demo.py:30: DeprecationWarning: The current add API output format is deprecated. To use the latest format, set `api_version='v1.1'`. The current format will be removed in mem0ai 1.1.0 and later versions.
  result = m.add("I am learning how to code. Suggest some tutorials.", user_id="alice", metadata={"category": "hobbies"})
[{'id': '48d3da4f-5762-4b7e-81e7-08f1f698e1a9', 'memory': 'Learning how to code', 'event': 'ADD'}]
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/embeddings "HTTP/1.1 200 OK"
INFO:mem0.vector_stores.mongodb:Vector search completed. Found 2 documents.
INFO:mem0.vector_stores.mongodb:Search results: [{'_id': '77d4c3ff-db16-4605-9165-953ea52ca959', 'id': '77d4c3ff-db16-4605-9165-953ea52ca959', 'payload': {'category': 'hobbies', 'user_id': 'alice', 'data': 'Working on improving tennis skills', 'hash': '4c3bc9f87b78418f19df6407bc86e006', 'created_at': '2025-01-25T15:59:26.421905-08:00'}, 'score': 0.7863138914108276}, {'_id': '48d3da4f-5762-4b7e-81e7-08f1f698e1a9', 'id': '48d3da4f-5762-4b7e-81e7-08f1f698e1a9', 'payload': {'category': 'hobbies', 'user_id': 'alice', 'data': 'Learning how to code', 'hash': 'df46e08f5b2caba0a9b1adf88465ec95', 'created_at': '2025-01-25T15:59:29.566151-08:00'}, 'score': 0.5650542378425598}]
/Users/fabianvalle/dev/OPENSOURCE/mem0/demo.py:33: DeprecationWarning: The current get_all API output format is deprecated. To use the latest format, set `api_version='v1.1'`. The current format will be removed in mem0ai 1.1.0 and later versions.
  related_memories = m.search(query="tennis", user_id="alice")
[{'id': '77d4c3ff-db16-4605-9165-953ea52ca959', 'memory': 'Working on improving tennis skills', 'hash': '4c3bc9f87b78418f19df6407bc86e006', 'metadata': {'category': 'hobbies'}, 'score': 0.7863138914108276, 'created_at': '2025-01-25T15:59:26.421905-08:00', 'updated_at': None, 'user_id': 'alice'}, {'id': '48d3da4f-5762-4b7e-81e7-08f1f698e1a9', 'memory': 'Learning how to code', 'hash': 'df46e08f5b2caba0a9b1adf88465ec95', 'metadata': {'category': 'hobbies'}, 'score': 0.5650542378425598, 'created_at': '2025-01-25T15:59:29.566151-08:00', 'updated_at': None, 'user_id': 'alice'}]
"""