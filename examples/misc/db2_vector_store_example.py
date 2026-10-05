"""IBM Db2 + mem0 — end-to-end memory example.

Demonstrates the full mem0 pipeline backed by IBM Db2 AI Vector Search.
Uses mem0's public API exclusively:
    Memory.add()        — extract facts with an LLM, embed, store in Db2
    Memory.get_all()    — list all memories for a user
    Memory.get()        — fetch a single memory by ID
    Memory.search()     — embed query, VECTOR_DISTANCE() search in Db2
                          filter operators: eq, ne, gt, gte, lt, lte,
                          in, nin, contains, icontains, $and, $or, $not
    Memory.history()    — change history for a memory
    Memory.update()     — update a stored memory
    Memory.delete()     — remove a memory
    Memory.delete_all() — wipe all memories for a user

keyword_search()        — full-text search via Db2 Text Search addon
                          (probed at startup; gracefully skipped when addon
                          is not installed — no error, just informational)

Providers used (configurable via env vars):
    LLM      → OpenAI gpt-4o-mini  (set OPENAI_API_KEY)
               or swap for Ollama  (set LLM_PROVIDER=ollama)
    Embedder → OpenAI text-embedding-3-small  (1536 dims)
               or swap for Ollama  (set EMBEDDER_PROVIDER=ollama)
    Store    → IBM Db2 AI Vector Search  (mem0/vector_stores/db2.py)

Requirements:
    pip install mem0ai ibm_db openai

Environment variables:
    OPENAI_API_KEY   — required when using OpenAI (default)
    DB2_HOST         — Db2 hostname            (default: 127.0.0.1)
    DB2_PORT         — Db2 TCP port            (default: 50000)
    DB2_DATABASE     — Db2 database name       (default: TESTDB)
    DB2_USERNAME     — Db2 user                (default: db2inst1)
    DB2_PASSWORD     — Db2 password            (required)

    # Ollama overrides (optional)
    LLM_PROVIDER     — set to "ollama" to use Ollama instead of OpenAI
    EMBEDDER_PROVIDER — set to "ollama" to use Ollama instead of OpenAI
    OLLAMA_BASE_URL  — Ollama URL             (default: http://localhost:11434)

Quickstart — Db2 Community Edition on Podman:
    podman run -itd --name db2server \\
      -e DB2INST1_PASSWORD=pass -e DBNAME=TESTDB -e LICENSE=accept \\
      -p 50000:50000 --privileged icr.io/db2_community/db2

    export OPENAI_API_KEY=sk-...
    export DB2_PASSWORD=pass
    python examples/misc/db2_vector_store_example.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("db2_mem0_example")

# Silence noisy third-party loggers
for _noisy in ("ibm_db_dbi", "urllib3", "httpx", "openai", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Optional .env loader
# ---------------------------------------------------------------------------
_ENV_FILE = Path(__file__).parent / ".env"
if _ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_FILE, override=False)
        log.info("Loaded env from %s", _ENV_FILE)
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Connection + provider config (from environment)
# ---------------------------------------------------------------------------
_DB2_PARAMS = {
    "host":     os.environ.get("DB2_HOST", "127.0.0.1"),
    "port":     int(os.environ.get("DB2_PORT", "50000")),
    "database": os.environ.get("DB2_DATABASE", "TESTDB"),
    "username": os.environ.get("DB2_USERNAME", "db2inst1"),
    "password": os.environ.get("DB2_PASSWORD", ""),
    # SSL/TLS — uncomment for IBM Cloud / Db2 on Cloud encrypted connections:
    # "security": True,
    # "ssl_cert": "/path/to/server.arm",   # path to the server certificate
}

# ---------------------------------------------------------------------------
# Alternative: reuse a pre-built ibm_db_dbi connection (e.g. from a pool)
# ---------------------------------------------------------------------------
# import ibm_db_dbi
# _EXISTING_CONN = ibm_db_dbi.connect(
#     "DATABASE=MYDB;HOSTNAME=...;PORT=50000;PROTOCOL=TCPIP;"
#     "UID=db2user;PWD=secret;Authentication=SERVER;",
#     "", "",
# )
# Then pass  client=_EXISTING_CONN  instead of  connection_params=_DB2_PARAMS
# in the vector_store config below.  mem0 will use it as-is and never close it.

_OLLAMA_URL      = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_LLM_PROVIDER    = os.environ.get("LLM_PROVIDER", "openai").lower()
_EMBED_PROVIDER  = os.environ.get("EMBEDDER_PROVIDER", "openai").lower()

# Embedding dims depend on the chosen provider
_EMBED_DIMS = 768 if _EMBED_PROVIDER == "ollama" else 1536


def _build_config() -> dict:
    """Assemble the mem0 config dict based on environment variables."""

    # ── LLM ──────────────────────────────────────────────────────────────────
    if _LLM_PROVIDER == "ollama":
        llm_cfg = {
            "provider": "ollama",
            "config": {
                "model":           "llama3.2",
                "ollama_base_url": _OLLAMA_URL,
                "temperature":     0,
                "max_tokens":      2000,
            },
        }
    else:  # openai (default)
        llm_cfg = {
            "provider": "openai",
            "config": {
                "model":       "gpt-4o-mini",
                "temperature": 0,
                "max_tokens":  2000,
            },
        }

    # ── Embedder ──────────────────────────────────────────────────────────────
    if _EMBED_PROVIDER == "ollama":
        embedder_cfg = {
            "provider": "ollama",
            "config": {
                "model":           "nomic-embed-text",
                "ollama_base_url": _OLLAMA_URL,
                "embedding_dims":  768,
            },
        }
    else:  # openai (default)
        embedder_cfg = {
            "provider": "openai",
            "config": {
                "model":          "text-embedding-3-small",
                "embedding_dims": 1536,
            },
        }

    # ── Vector store — always IBM Db2 ─────────────────────────────────────────
    vector_store_cfg = {
        "provider": "db2",
        "config": {
            "collection_name":      "mem0_example",
            "embedding_model_dims": _EMBED_DIMS,
            # distance_strategy options: EUCLIDEAN (default), COSINE, DOT,
            # EUCLIDEAN_DISTANCE, HAMMING, MANHATTAN.
            "distance_strategy":    "COSINE",
            "connection_params":    _DB2_PARAMS,
            # use_vector_index: enable native ANN index for large collections.
            # Requires Db2 12.1.5+ Standard/Advanced Edition (NOT CE containers).
            # Only compatible with COSINE, EUCLIDEAN, EUCLIDEAN_DISTANCE.
            # "use_vector_index": True,
        },
    }

    return {
        "llm":          llm_cfg,
        "embedder":     embedder_cfg,
        "vector_store": vector_store_cfg,
    }


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------
_CONVERSATIONS = [
    {
        "user_id": "alice",
        "messages": [
            {"role": "user",      "content": "I just adopted a golden retriever puppy named Max. He loves playing fetch."},
            {"role": "assistant", "content": "How lovely! How old is Max?"},
            {"role": "user",      "content": "He's 3 months old. I'm also vegetarian and allergic to nuts."},
        ],
    },
    {
        "user_id": "bob",
        "messages": [
            {"role": "user",      "content": "I'm a senior Python engineer at a fintech startup."},
            {"role": "assistant", "content": "Exciting! What are you building?"},
            {"role": "user",      "content": "Data pipelines with Apache Spark. I adopted two rescue cats last summer."},
        ],
    },
    {
        "user_id": "charlie",
        "messages": [
            {"role": "user",      "content": "I'm 28 years old and I run marathons every spring."},
            {"role": "assistant", "content": "Impressive! How long have you been running?"},
            {"role": "user",      "content": "About 5 years. I also cycle to work daily and prefer high-protein meals."},
        ],
    },
]

_QUERIES = [
    ("alice", "What are Alice's dietary restrictions?"),
    ("alice", "Does Alice have any pets?"),
    ("bob",   "What does Bob do for work?"),
    ("bob",   "Does Bob have any pets?"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sep(title: str) -> None:
    print(f"\n{'═' * 65}\n  {title}\n{'═' * 65}")


def _subsep(title: str) -> None:
    print(f"\n  {'─' * 55}\n  {title}\n  {'─' * 55}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # Pre-flight checks
    if not _DB2_PARAMS["password"]:
        log.error("DB2_PASSWORD is not set.  Export it before running:\n  export DB2_PASSWORD=<your-password>")
        sys.exit(1)
    if _LLM_PROVIDER == "openai" and not os.environ.get("OPENAI_API_KEY"):
        log.error("OPENAI_API_KEY is not set.  Export it or switch to Ollama:\n  export LLM_PROVIDER=ollama")
        sys.exit(1)

    config = _build_config()

    _sep("Configuration")
    print(f"  LLM provider      : {_LLM_PROVIDER}")
    print(f"  Embedder provider : {_EMBED_PROVIDER}  ({_EMBED_DIMS} dims)")
    print(f"  Vector store      : IBM Db2  {_DB2_PARAMS['host']}:{_DB2_PARAMS['port']}/{_DB2_PARAMS['database']}")
    print(f"  Table             : {config['vector_store']['config']['collection_name']}")
    print(f"  Distance          : {config['vector_store']['config']['distance_strategy']}")

    # ── 1. Initialise ─────────────────────────────────────────────────────────
    _sep("1. Initialise mem0 Memory")
    from mem0 import Memory
    m = Memory.from_config(config)
    log.info("Memory initialised — VectorStore: %s", m.vector_store.__class__.__name__)
    print(f"  ✅  mem0 Memory ready  (table: {m.vector_store.config.collection_name})")

    # ── 2. Memory.add() ───────────────────────────────────────────────────────
    _sep("2. Memory.add()  — extract facts, embed, store in Db2")
    all_ids: dict[str, list[str]] = {}
    for conv in _CONVERSATIONS:
        user_id = conv["user_id"]
        msgs    = conv["messages"]
        _subsep(f"user_id = {user_id}")
        print("  Input conversation:")
        for msg in msgs:
            print(f"    [{msg['role']:>9}] {msg['content']}")

        result = m.add(msgs, user_id=user_id)
        added  = result.get("results", []) if isinstance(result, dict) else result

        print(f"\n  Extracted & stored memories ({len(added)}):")
        all_ids[user_id] = []
        for mem in added:
            mem_text = mem.get("memory", mem.get("text", str(mem)))
            mem_id   = str(mem.get("id", "?"))
            event    = mem.get("event", "ADD")
            print(f"    [{event:>6}]  id={mem_id[:24]}  \"{mem_text}\"")
            log.info("  stored: user=%s  event=%s  id=%s  text=%s", user_id, event, mem_id, mem_text)
            all_ids[user_id].append(mem_id)

    # ── 3. Memory.get_all() ───────────────────────────────────────────────────
    _sep("3. Memory.get_all()  — list all stored memories per user")
    for user_id in [c["user_id"] for c in _CONVERSATIONS]:
        res  = m.get_all(filters={"user_id": user_id})
        mems = res.get("results", []) if isinstance(res, dict) else res
        print(f"\n  user_id={user_id}  ({len(mems)} memories):")
        for mem in mems:
            print(f"    • {mem.get('memory', mem.get('text', str(mem)))}")

    # ── 4. Memory.search() — simple per-user filter ───────────────────────────
    _sep("4. Memory.search()  — embed query → VECTOR_DISTANCE() in Db2")
    for user_id, query in _QUERIES:
        _subsep(f"user_id={user_id}  |  \"{query}\"")
        results = m.search(query=query, filters={"user_id": user_id}, top_k=3)
        hits    = results.get("results", []) if isinstance(results, dict) else results
        if hits:
            for r in hits:
                score   = r.get("score", 0.0)
                mem_txt = r.get("memory", r.get("text", str(r)))
                print(f"    score={score:.4f}  \"{mem_txt}\"")
        else:
            print("    (no memories found)")

    # ── 4b. Memory.search() — compound metadata filters ──────────────────────
    # ── 4b. Memory.search() — metadata operator filters ──────────────────────
    # NOTE: user_id / agent_id / run_id are mandatory scope selectors — they
    # must always be flat strings at the top level of filters{}.
    # Operator filters (eq, ne, gt, contains, AND, OR, NOT …) apply to custom
    # metadata fields stored alongside each memory, not to user_id itself.
    _sep("4b. Memory.search()  — metadata operator filters (contains, ne, AND, OR, NOT)")

    # contains — alice's memories where data text contains 'retriever'
    # mem0 stores the extracted text under the "data" key in metadata
    _subsep("contains — user_id=alice, data contains 'retriever'")
    res = m.search(
        query="pet",
        filters={"user_id": "alice", "data": {"contains": "retriever"}},
        top_k=5,
    )
    hits = res.get("results", []) if isinstance(res, dict) else res
    for r in hits:
        print(f"    score={r.get('score', 0.0):.4f}  \"{r.get('memory', '')}\"")
    if not hits:
        print("    (no memories found)")

    # ne — bob's memories where data is not the cats entry
    _subsep("ne — user_id=bob, data ne 'User adopted two rescue cats last summer'")
    res = m.search(
        query="work",
        filters={"user_id": "bob", "data": {"ne": "User adopted two rescue cats last summer"}},
        top_k=5,
    )
    hits = res.get("results", []) if isinstance(res, dict) else res
    for r in hits:
        print(f"    score={r.get('score', 0.0):.4f}  \"{r.get('memory', '')}\"")
    if not hits:
        print("    (no memories found)")

    # AND — charlie, data contains 'marathon' AND contains 'year'
    _subsep("AND — user_id=charlie, data contains 'marathon' AND contains 'year'")
    res = m.search(
        query="running",
        filters={
            "user_id": "charlie",
            "AND": [
                {"data": {"contains": "marathon"}},
                {"data": {"contains": "year"}},
            ],
        },
        top_k=5,
    )
    hits = res.get("results", []) if isinstance(res, dict) else res
    for r in hits:
        print(f"    score={r.get('score', 0.0):.4f}  \"{r.get('memory', '')}\"")
    if not hits:
        print("    (no memories found)")

    # OR — alice, data contains 'vegetarian' OR contains 'retriever'
    _subsep("OR — user_id=alice, data contains 'vegetarian' OR contains 'retriever'")
    res = m.search(
        query="alice",
        filters={
            "user_id": "alice",
            "OR": [
                {"data": {"contains": "vegetarian"}},
                {"data": {"contains": "retriever"}},
            ],
        },
        top_k=5,
    )
    hits = res.get("results", []) if isinstance(res, dict) else res
    for r in hits:
        print(f"    score={r.get('score', 0.0):.4f}  \"{r.get('memory', '')}\"")
    if not hits:
        print("    (no memories found)")

    # NOT — charlie, exclude memories where data contains 'cycle'
    _subsep("NOT — user_id=charlie, exclude data containing 'cycle'")
    res = m.search(
        query="exercise",
        filters={
            "user_id": "charlie",
            "NOT": [{"data": {"contains": "cycle"}}],
        },
        top_k=5,
    )
    hits = res.get("results", []) if isinstance(res, dict) else res
    for r in hits:
        print(f"    score={r.get('score', 0.0):.4f}  \"{r.get('memory', '')}\"")
    if not hits:
        print("    (no memories found)")

    # gt/gte/lt/lte — range operators on numeric custom metadata fields.
    # Insert a record directly via Db2VectorStore so we control the numeric fields.
    _subsep("gt/gte/lt/lte range filters on custom numeric metadata")
    print("  (inserting records with explicit numeric fields via Db2VectorStore.insert)")
    from mem0.vector_stores.db2 import Db2VectorStore
    import ibm_db_dbi
    _cp = _DB2_PARAMS
    _conn_str = (
        f"DATABASE={_cp['database']};HOSTNAME={_cp['host']};PORT={_cp['port']};"
        f"PROTOCOL=TCPIP;UID={_cp['username']};PWD={_cp['password']};Authentication=SERVER;"
    )
    _raw_conn = ibm_db_dbi.connect(_conn_str, "", "")
    _vs = Db2VectorStore(
        client=_raw_conn,
        collection_name=m.vector_store.config.collection_name,
        embedding_model_dims=_EMBED_DIMS,
        distance_strategy="COSINE",
    )
    _vs.insert(
        vectors=[[0.5] * _EMBED_DIMS],
        payloads=[{"data": "Numeric filter test", "user_id": "alice", "age": 30, "confidence": 0.95}],
    )
    # gt: age > 25 — scoped to alice
    res = m.search(query="test", filters={"user_id": "alice", "age": {"gt": 25}}, top_k=5)
    hits = res.get("results", []) if isinstance(res, dict) else res
    print(f"    age > 25        → {len(hits)} result(s)")
    # gte: confidence >= 0.9
    res = m.search(query="test", filters={"user_id": "alice", "confidence": {"gte": 0.9}}, top_k=5)
    hits = res.get("results", []) if isinstance(res, dict) else res
    print(f"    confidence >= 0.9 → {len(hits)} result(s)")
    # lt / lte
    res = m.search(query="test", filters={"user_id": "alice", "age": {"lt": 35}}, top_k=5)
    hits = res.get("results", []) if isinstance(res, dict) else res
    print(f"    age < 35        → {len(hits)} result(s)")
    res = m.search(query="test", filters={"user_id": "alice", "confidence": {"lte": 1.0}}, top_k=5)
    hits = res.get("results", []) if isinstance(res, dict) else res
    print(f"    confidence <= 1.0 → {len(hits)} result(s)")
    _raw_conn.close()

    # ── 4c. keyword_search() — Db2 Text Search (informational) ───────────────
    _sep("4c. keyword_search()  — Db2 Text Search addon")
    # keyword_search() is probed once at startup (_probe_text_search).
    # It returns None when the Text Search addon is not installed — mem0
    # automatically falls back to semantic-only search in that case.
    # No error is raised; this step is purely informational.
    ts_available = m.vector_store._text_search_available
    if ts_available:
        print("  Db2 Text Search addon: AVAILABLE")
        kw_results = m.vector_store.keyword_search(
            query="retriever vegetarian",
            top_k=5,
            filters={"user_id": "alice"},
        )
        if kw_results:
            print(f"  keyword_search results ({len(kw_results)}):")
            for r in kw_results:
                print(f"    score={r.score:.4f}  \"{r.payload.get('data', '')}\"")
        else:
            print("  keyword_search returned no results (index may not exist yet).")
        print("""
  To create the Text Search index on the mem0 table:
    CALL SYSPROC.SYSTS_CREATE(
        CURRENT SCHEMA, 'MEM0_EXAMPLE', 'text_lemmatized',
        'MAXIMUM CHARACTERS 10000 LANGUAGE EN FORMAT NONE'
    );
""")
    else:
        print("  Db2 Text Search addon: NOT INSTALLED")
        print("  keyword_search() returns None — mem0 uses semantic-only search.")
        print("  To enable: install the Db2 Text Search addon and create an index:")
        print("    CALL SYSPROC.SYSTS_CREATE(")
        print(f"        CURRENT SCHEMA, '{m.vector_store.config.collection_name.upper()}',")
        print("        'text_lemmatized', 'MAXIMUM CHARACTERS 10000 LANGUAGE EN FORMAT NONE'")
        print("    );")

    # ── 5. Memory.get()  — fetch a single memory by ID ───────────────────────
    _sep("5. Memory.get()  — fetch a single memory by ID")
    alice_ids = all_ids.get("alice", [])
    if alice_ids:
        mem_id = alice_ids[0]
        single = m.get(memory_id=mem_id)
        if single:
            mem_txt = single.get("memory", single.get("text", str(single)))
            print(f"  id    = {mem_id}")
            print(f"  text  = \"{mem_txt}\"")
            log.info("get(%s) → %s", mem_id, mem_txt)
        else:
            print(f"  Memory {mem_id} not found.")
    else:
        print("  No alice memories to fetch.")

    # ── 6. Memory.history() — change log for a memory ────────────────────────
    _sep("6. Memory.history()  — change log for Alice's first memory")
    if alice_ids:
        mem_id  = alice_ids[0]
        history = m.history(memory_id=mem_id)
        hist_list = history.get("results", history) if isinstance(history, dict) else history
        print(f"  History entries for id={mem_id[:24]}  ({len(hist_list)} events):")
        for entry in hist_list:
            evt      = entry.get("event", entry.get("action", "?"))
            old_mem  = entry.get("old_memory") or "—"
            new_mem  = entry.get("new_memory") or entry.get("memory", "—")
            print(f"    [{evt:>6}]  old: \"{old_mem}\"  →  new: \"{new_mem}\"")
    else:
        print("  No alice memories for history.")

    # ── 7. Memory.update() ────────────────────────────────────────────────────
    _sep("7. Memory.update()  — update Alice's first memory")
    if alice_ids:
        mem_id   = alice_ids[0]
        new_text = "Alice has a golden retriever named Max (now 4 months old) who loves fetch and frisbee."
        log.info("Updating memory id=%s for alice ...", mem_id)
        m.update(memory_id=mem_id, text=new_text)
        updated  = m.get(memory_id=mem_id)
        upd_text = updated.get("memory", updated.get("text", str(updated))) if updated else "not found"
        print(f"  Updated → \"{upd_text}\"")
    else:
        print("  No alice memories to update.")

    # ── 8. Memory.delete() ────────────────────────────────────────────────────
    _sep("8. Memory.delete()  — delete Bob's first memory")
    bob_ids = all_ids.get("bob", [])
    if bob_ids:
        del_id = bob_ids[0]
        log.info("Deleting memory id=%s for bob ...", del_id)
        m.delete(memory_id=del_id)
        gone = m.get(memory_id=del_id)
        print(f"  Deleted id={del_id[:24]}  — still exists: {gone is not None}")
    else:
        print("  No bob memories to delete.")

    # ── 9. Memory.delete_all() ────────────────────────────────────────────────
    _sep("9. Memory.delete_all()  — wipe all Alice's memories")
    m.delete_all(user_id="alice")
    after = m.get_all(filters={"user_id": "alice"})
    after_list = after.get("results", []) if isinstance(after, dict) else after
    print(f"  Alice memories after delete_all: {len(after_list)}  (expected 0)")
    log.info("delete_all alice: %d memories remain", len(after_list))

    # ── Done ──────────────────────────────────────────────────────────────────
    _sep("Done")
    print("  mem0 + IBM Db2 example completed successfully.")
    log.info("Example finished successfully")


if __name__ == "__main__":
    main()
