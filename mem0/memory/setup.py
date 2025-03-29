import json
import os
import uuid

# Set up the directory path
VECTOR_ID = "fd411bd3-99a2-42d6-acd7-9fca8ad09580"
home_dir = os.path.expanduser("~")
mem0_dir = os.environ.get("MEM0_DIR") or os.path.join(home_dir, ".mem0")
os.makedirs(mem0_dir, exist_ok=True)


def setup_config():
    config_path = os.path.join(mem0_dir, "config.json")
    if not os.path.exists(config_path):
        user_id = str(uuid.uuid4())
        config = {"user_id": user_id}
        with open(config_path, "w") as config_file:
            json.dump(config, config_file, indent=4)


def get_user_id():
    config_path = os.path.join(mem0_dir, "config.json")
    if not os.path.exists(config_path):
        return "anonymous_user"

    try:
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
            user_id = config.get("user_id")
            return user_id
    except Exception:
        return "anonymous_user"


def store_and_get_user_id_from_vector_store(vector_store):
    """Store user_id in mem0_migrations collection."""
    user_id = get_user_id()
    try:
        try:
            existing = vector_store.get(vector_id=VECTOR_ID)

            if existing and hasattr(existing, "payload") and existing.payload and "user_id" in existing.payload:
                return existing.payload["user_id"]
        except Exception as e:
            pass

        dims = 1
        if hasattr(vector_store, "embedding_model_dims"):
            dims = vector_store.embedding_model_dims

        vector_store.insert(
            vectors=[[0.0] * dims], payloads=[{"user_id": user_id, "type": "user_identity"}], ids=[VECTOR_ID]
        )
        return user_id
    except Exception as e:
        return user_id
