# Sandbox — infrastructure regression suite

Runs the real `Memory` engine against **real vector stores in containers**, asserting the
scoping, filter-translation and deletion behaviour that `audit.md` found broken. Every
assertion runs against **each** store, so store-to-store divergence shows up as a failure
rather than as a support ticket.

```bash
docker compose -f sandbox/docker-compose.yml up -d
pytest sandbox/
```

Stores that aren't reachable are skipped, so a partial stack still gives a useful run.

## No LLM, no API keys, no Azure

Nothing here talks to a model provider, by design.

Every bug this suite targets — delete scoping, tenancy isolation, metadata-filter
translation, `reset()`, entity-id preservation on `update()` — lives **below** the LLM. The
LLM's only job is deciding which facts to extract from a message; it has no influence on how
a filter becomes a SQL `WHERE` clause or a Qdrant condition. Pointing a real provider at
these tests would buy nothing and cost determinism (extraction varies run to run, so
assertions flake), money per run, a secret that fork PRs can't have, and latency.

So the suite uses:

- **`infer=False`** on every write, which stores the message verbatim and makes zero LLM calls.
- **`HashEmbedder`** in `conftest.py` — a token-hash embedding that is deterministic, content-sensitive
  (overlapping text ranks higher, so search-ordering assertions are meaningful) and entirely local.

Real embeddings would only change *semantic relevance quality*, which is a model question,
not an infrastructure bug. Add an opt-in provider-backed test when someone needs to
regression-test prompt or extraction changes; that is a different suite from this one.

One wrinkle worth knowing: `audit.md` M-14 is real, so a custom embedder cannot be injected
through config (the provider allow-lists in `mem0/embeddings/configs.py` are hardcoded
Pydantic literals that `EmbedderFactory` never consults for registration). The fixture works
around it by constructing `Memory` normally and swapping `embedding_model` afterwards. The
dummy `OPENAI_API_KEY` exists purely so the unused default provider can be constructed.

## Known-broken cases

Confirmed defects are marked `xfail` rather than deleted, so the suite is green today and
flips to `XPASS` the moment someone fixes one:

| Test | Finding |
|---|---|
| `test_icontains_is_case_insensitive` | audit O3 — `icontains` maps to a case-sensitive `MatchText` on Qdrant. **Passes on pgvector**, so the two stores disagree. |
| `test_wildcard_requires_the_field_to_exist` | audit O4 — `*` is a no-op match-all on Qdrant instead of an existence check. **Passes on pgvector**, so the two stores disagree. |
| `test_or_filter_matches_either_branch_via_get_all` | Found by this suite. `search()` normalises `OR` → `$or` via `_process_filters`; `get_all()` passes filters straight to `vector_store.list()` (`mem0/memory/main.py:1297`) with no normalisation. Qdrant self-normalises and survives; pgvector only recognises `$or`, so the raw `OR` key falls through to an equality comparison and **silently returns zero rows**. The sibling `..._via_search` test passes on both stores, which is the evidence of the asymmetry. |
