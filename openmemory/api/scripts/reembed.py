"""
Re-embed all memories into a fresh Qdrant collection (embedder migration).

Switching the embedding model changes the vector space (and usually the dim), so
vectors are NOT cross-model compatible — every memory must be re-embedded into a
NEW collection. Postgres is the source of truth for memory content, so this is
lossless. The new collection is created by mem0 with the BM25 sparse slot, so the
migration also ACTIVATES hybrid search.

Zero-downtime cutover:
  1. Deploy with the NEW embedder + a NEW collection name, pointed so this script
     can build the client, but keep the live app on the OLD collection until done:
        EMBEDDER_PROVIDER=fastembed
        EMBEDDER_MODEL=snowflake/snowflake-arctic-embed-m
        EMBEDDING_DIMS=768
        QDRANT_COLLECTION_NAME=openmemory_arctic_m_768   # NEW name, not 'openmemory'
  2. Run:  python -m scripts.reembed            (add --dry-run first to preview)
  3. Verify counts, then point the live app at QDRANT_COLLECTION_NAME=openmemory_arctic_m_768
     and redeploy. Delete the old collection once validated.

Idempotent: re-running upserts by the same memory id, so it is safe to resume.
"""

import argparse
import datetime
import hashlib
import os
import sys

# Ensure the api package root is importable when run as `python scripts/reembed.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import Memory, MemoryState, User  # noqa: E402
from app.utils.memory import get_memory_client  # noqa: E402

try:
    from mem0.utils.lemmatization import lemmatize_for_bm25
except Exception:  # pragma: no cover
    def lemmatize_for_bm25(text: str) -> str:
        return text


def _iso(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    return str(dt)


def reembed(batch_log: int = 100, dry_run: bool = False) -> None:
    client = get_memory_client()
    if client is None:
        raise SystemExit("Memory client unavailable — check embedder/Qdrant env vars.")

    vs = client.vector_store
    collection = getattr(vs, "collection_name", "?")
    dims = os.environ.get("EMBEDDING_DIMS", "1536 (default)")
    embedder = os.environ.get("EMBEDDER_MODEL", os.environ.get("EMBEDDER_PROVIDER", "openai default"))
    print(f"Target collection : {collection}")
    print(f"Embedding dims     : {dims}")
    print(f"Embedder           : {embedder}")
    if collection == "openmemory":
        print("WARNING: target is the default 'openmemory' collection. For a safe cutover, "
              "set QDRANT_COLLECTION_NAME to a NEW name before running.")

    db = SessionLocal()
    try:
        rows = (
            db.query(Memory, User.user_id)
            .join(User, Memory.user_id == User.id)
            .filter(Memory.state == MemoryState.active)
            .all()
        )
        total = len(rows)
        print(f"Active memories to re-embed: {total}")
        if dry_run:
            print("--dry-run: no writes performed.")
            return

        done = 0
        for mem, user_id_str in rows:
            content = mem.content or ""
            if not content.strip():
                continue
            embedding = client.embedding_model.embed(content, "add")
            payload = {
                "data": content,
                "hash": hashlib.md5(content.encode()).hexdigest(),
                "user_id": user_id_str,
                "created_at": _iso(mem.created_at),
                "updated_at": _iso(mem.updated_at),
                "text_lemmatized": lemmatize_for_bm25(content),
            }
            # Preserve the original Postgres id so existing references stay valid.
            vs.insert(vectors=[embedding], payloads=[payload], ids=[str(mem.id)])
            done += 1
            if done % batch_log == 0:
                print(f"  re-embedded {done}/{total}")

        print(f"Done. Re-embedded {done}/{total} memories into '{collection}'.")
        print("Next: point the app at this collection (QDRANT_COLLECTION_NAME) and redeploy, "
              "then delete the old collection once validated.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-embed memories into a fresh Qdrant collection.")
    parser.add_argument("--dry-run", action="store_true", help="Count only; do not write.")
    parser.add_argument("--batch-log", type=int, default=100, help="Progress log interval.")
    args = parser.parse_args()
    reembed(batch_log=args.batch_log, dry_run=args.dry_run)
