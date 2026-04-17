"""
Minimal runnable example for using Mem0 with Oracle Autonomous AI Database
as the vector store, including agent-scoped add/search with a real embedding provider.

WHAT THIS EXAMPLE DOES:
- Connects Mem0 to Oracle Autonomous AI Database using an Oracle wallet
- Uses FastEmbed as the embedding provider
- Stores memory with an agent_id
- Searches memory back with the same agent_id
- Uses infer=False so the example runs without an LLM API key

WHEN TO USE THIS:
- When validating Mem0 integration with Oracle Autonomous AI Database
- When checking Python wallet-based connectivity
- When verifying agent-scoped memory add/search end to end
- When you want a minimal Oracle vector store example before enabling infer=True

SETUP INSTRUCTIONS:
1. Download the Oracle Autonomous AI Database wallet and unzip it locally.
2. Set environment variables:
   export ORACLE_WALLET_DIR="/path/to/your-aidb-wallet"
   export ORACLE_WALLET_PASSWORD="your-wallet-password"
   export ORACLE_DB_USER="your-db-user"
   export ORACLE_DB_PASSWORD="your-db-password"
   export ORACLE_AIDB_DSN="your_aidb_high"
3. Install the embedding dependency:
   pip install fastembed
4. Run the example:
   python examples/misc/oracle_aidb_agent_memory.py
"""

import os
import uuid

from mem0 import Memory


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise KeyError(name)
    return value


os.environ["MEM0_TELEMETRY"] = "false"

WALLET_DIR = require_env("ORACLE_WALLET_DIR")
WALLET_PASSWORD = require_env("ORACLE_WALLET_PASSWORD")
DB_USER = require_env("ORACLE_DB_USER")
DB_PASSWORD = require_env("ORACLE_DB_PASSWORD")
DSN = require_env("ORACLE_AIDB_DSN")

COLLECTION_NAME = f"mem0_oracle_aidb_demo_{uuid.uuid4().hex[:8]}"
AGENT_ID = f"oracle-agent-{uuid.uuid4().hex[:8]}"

config = {
    "embedder": {
        "provider": "fastembed",
        "config": {
            "model": "BAAI/bge-small-en-v1.5",
            "embedding_dims": 384,
        },
    },
    "vector_store": {
        "provider": "oracle",
        "config": {
            "dsn": DSN,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "config_dir": WALLET_DIR,
            "wallet_location": WALLET_DIR,
            "wallet_password": WALLET_PASSWORD,
            "collection_name": COLLECTION_NAME,
            "embedding_model_dims": 384,
            "distance": "COSINE",
            "search_mode": "approx",
            "auto_create": True,
            "index_fallback_to_exact": True,
            "index": {
                "create": True,
                "type": "hnsw",
                "target_accuracy": 90,
                "neighbors": 32,
                "efconstruction": 200,
            },
        },
    },
}


def main():
    print(f"--> Initializing Mem0 with Oracle Autonomous AI Database collection: {COLLECTION_NAME}")
    memory = Memory.from_config(config)
    print("--> Memory initialized successfully")

    text = "This OCI agent prefers Oracle AI Database vector search for durable memory."
    print(f"--> Adding memory for agent_id={AGENT_ID}")
    add_result = memory.add(
        text,
        agent_id=AGENT_ID,
        infer=False,
        metadata={
            "scope": "agent-demo",
            "environment": "oci",
            "embedding_provider": "fastembed",
        },
    )
    print("Add result:")
    print(add_result)

    query = "What vector store should this OCI agent prefer?"
    print(f"--> Searching memories for agent_id={AGENT_ID}")
    search_result = memory.search(
        query=query,
        filters={"agent_id": AGENT_ID},
        top_k=3,
    )
    print("Search result:")
    print(search_result)

    print("--> Done")


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        print(f"Missing required environment variable: {e}")
    except Exception as e:
        print(f"Error: {e}")
