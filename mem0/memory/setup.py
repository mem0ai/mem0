import os
import uuid
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.vector_stores.qdrant import Qdrant
from datetime import datetime

# Set up the directory path
home_dir = os.path.expanduser("~")
mem0_dir = os.environ.get("MEM0_DIR") or os.path.join(home_dir, ".mem0")
os.makedirs(mem0_dir, exist_ok=True)
USER_CONFIG_COLLECTION = "user_config"

def setup_config():
    """Set up user configuration using vector store"""
    config = VectorStoreConfig(config={"collection_name": USER_CONFIG_COLLECTION})
    vector_store = Qdrant(**config.config.dict())

    user_id = str(uuid.uuid4())
    metadata = {
        "type": "user_config",
        "user_id": user_id,
        "created_at": datetime.now().isoformat()
    }

    # Store empty vector with user metadata
    vectors = [[0.0] * 1536]
    vector_store.insert(
        vectors=vectors,
        payloads=[metadata],
        ids=[user_id]
    )
    return user_id

def get_user_id():
    """Retrieve user ID from vector store"""
    config = VectorStoreConfig(config={"collection_name": USER_CONFIG_COLLECTION})
    vector_store = Qdrant(**config.config.dict())
    try:
        # Search for user config entry using empty vector
        query_vector = [0.0] * 1536
        results = vector_store.search(
            query=query_vector,
            limit=1,
            filters={"type": "user_config"}
        )
        if results and len(results) > 0:
            return results[0].payload.get("user_id")

        # If no user found, create new one
        return setup_config()
    except Exception as e:
        print(f"Error retrieving user_id: {e}")
        return "anonymous_user"
