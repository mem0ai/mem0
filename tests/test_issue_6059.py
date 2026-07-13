from unittest.mock import MagicMock
from mem0.vector_stores.redis import RedisDB

db = RedisDB.__new__(RedisDB)          # bypass the live-Redis connection
db.index = MagicMock()

# A stored record that has updated_at, as update() persists it:
stored = {"memory_id": "m1", "hash": "h", "memory": "hello", "metadata": "{}",
          "created_at": 1_700_000_000, "updated_at": 1_700_000_050, "vector_distance": 0.1}

# Redis returns only the fields the query asks for:
def only_requested(query):
    fields = set(query._return_fields) | {"memory_id", "vector_distance"}
    return [{k: v for k, v in stored.items() if k in fields}]
db.index.query.side_effect = only_requested

payload = db.search("hello", [0.1, 0.2, 0.3, 0.4], top_k=1)[0].payload
print("search() payload includes updated_at:", "updated_at" in payload)
# main -> False.  get()/list() would return it. keyword_search() shares the same omission.
