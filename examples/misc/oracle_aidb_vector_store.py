"""
Standalone Oracle Autonomous AI Database vector store smoke test for Mem0.

WHAT THIS SCRIPT DOES:
- Connects to Oracle Autonomous AI Database using an Oracle wallet
- Uses FastEmbed to generate embeddings locally
- Creates a temporary OracleDB collection with HNSW indexing enabled
- Inserts sample memories with a user-scoped filter
- Runs a vector search and prints the returned results
- Prints the Oracle indexes created for the temporary collection
- Drops the temporary collection before exiting

WHEN TO USE THIS:
- When validating wallet-based connectivity from a fresh clone
- When checking Oracle AI Vector Search index creation in your environment
- When you want a low-level Oracle vector store smoke test before wiring a full Mem0 Memory config
- When you want to avoid LLM configuration and OpenAI API keys during the first integration check

SETUP INSTRUCTIONS:
1. Download the Oracle Autonomous AI Database wallet and unzip it locally.
2. Set environment variables:
   export ORACLE_WALLET_DIR="/path/to/your-aidb-wallet"
   export ORACLE_WALLET_PASSWORD="your-wallet-password"
   export ORACLE_DB_USER="your-db-user"
   export ORACLE_DB_PASSWORD="your-db-password"
   export ORACLE_AIDB_DSN="your_aidb_high"
3. Install the embedding dependency if needed:
   pip install fastembed
4. Run the script:
   python examples/misc/oracle_aidb_vector_store.py
"""

import datetime as dt
import hashlib
import json
import os
import uuid

from fastembed import TextEmbedding

from mem0.vector_stores.oracle import OracleDB


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise KeyError(name)
    return value


class FastEmbedAdapter:
    def __init__(self, model_name: str):
        self.model = TextEmbedding(model_name=model_name)
        self.dim = len(next(self.model.embed(["dimension probe"])).tolist())

    def embed(self, text: str) -> list[float]:
        vector = next(self.model.embed([text]))
        return vector.tolist() if hasattr(vector, "tolist") else list(vector)


def build_payload(text: str, user_id: str, topic: str) -> dict:
    timestamp = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    return {
        "data": text,
        "text_lemmatized": text.lower(),
        "user_id": user_id,
        "topic": topic,
        "hash": hashlib.md5(text.encode("utf-8")).hexdigest(),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


os.environ["MEM0_TELEMETRY"] = "false"

WALLET_DIR = require_env("ORACLE_WALLET_DIR")
WALLET_PASSWORD = require_env("ORACLE_WALLET_PASSWORD")
DB_USER = require_env("ORACLE_DB_USER")
DB_PASSWORD = require_env("ORACLE_DB_PASSWORD")
DSN = require_env("ORACLE_AIDB_DSN")

MODEL_NAME = "BAAI/bge-small-en-v1.5"
COLLECTION_NAME = f"M0AIDB_{uuid.uuid4().hex[:8]}".upper()
USER_ID = f"user_{uuid.uuid4().hex[:8]}"


def main():
    embedder = FastEmbedAdapter(MODEL_NAME)
    store = OracleDB(
        collection_name=COLLECTION_NAME,
        embedding_model_dims=embedder.dim,
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DSN,
        config_dir=WALLET_DIR,
        wallet_location=WALLET_DIR,
        wallet_password=WALLET_PASSWORD,
        distance="COSINE",
        search_mode="approx",
        target_accuracy=90,
        index_fallback_to_exact=True,
        index={
            "create": True,
            "type": "hnsw",
            "target_accuracy": 90,
            "neighbors": 32,
            "efconstruction": 200,
        },
    )

    rows = [
        {
            "id": f"mem_{uuid.uuid4().hex[:8]}",
            "payload": build_payload(
                "Oracle AI Vector Search uses HNSW indexes for approximate nearest neighbor retrieval.",
                USER_ID,
                "vector",
            ),
        },
        {
            "id": f"mem_{uuid.uuid4().hex[:8]}",
            "payload": build_payload(
                "Oracle Autonomous AI Database supports wallet based connections from OCI workloads.",
                USER_ID,
                "connectivity",
            ),
        },
    ]

    print(f"--> Oracle Autonomous AI Database smoke test collection: {COLLECTION_NAME}")
    print(f"--> Embedding model: {MODEL_NAME} ({embedder.dim} dimensions)")
    print(f"--> Inserting {len(rows)} vectors")

    try:
        store.insert(
            vectors=[embedder.embed(row["payload"]["data"]) for row in rows],
            payloads=[row["payload"] for row in rows],
            ids=[row["id"] for row in rows],
        )

        with store._get_cursor() as cur:
            cur.execute(
                """
                SELECT index_name, index_type
                FROM user_indexes
                WHERE table_name = :table_name
                ORDER BY index_name
                """,
                {"table_name": COLLECTION_NAME},
            )
            indexes = [{"name": row[0], "type": row[1]} for row in cur.fetchall()]

        query = "How does Oracle perform approximate vector retrieval?"
        print(f"--> Searching with user_id={USER_ID}")
        results = store.search(
            query=query,
            vectors=embedder.embed(query),
            top_k=3,
            filters={"user_id": USER_ID},
        )

        print("Indexes:")
        print(json.dumps(indexes, indent=2))

        print("Search results:")
        print(
            json.dumps(
                [
                    {
                        "id": result.id,
                        "score": result.score,
                        "data": (result.payload or {}).get("data"),
                        "topic": (result.payload or {}).get("topic"),
                    }
                    for result in results
                ],
                indent=2,
            )
        )
    finally:
        print(f"--> Dropping temporary collection: {COLLECTION_NAME}")
        with store._get_cursor(commit=True) as cur:
            cur.execute(f"DROP TABLE {COLLECTION_NAME} PURGE")


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        print(f"Missing required environment variable: {e}")
    except Exception as e:
        print(f"Error: {e}")
