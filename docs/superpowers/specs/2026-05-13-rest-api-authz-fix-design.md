# REST API Authorization Fix — Design

**Date:** 2026-05-13
**Branch (target):** `main`
**Scope:** `server/` (self-hosted OSS REST server) + `docs/open-source/features/rest-api.mdx`
**Trigger:** Security report from `vonbrubeck@gmail.com` (2026-05-01) titled
"Mem0 OSS REST per-user API keys can access and delete other users' memories."

## Problem

The self-hosted OSS REST server documents per-user API keys as "scoped to a
single dashboard user" (`docs/open-source/features/rest-api.mdx:131-136, 185`),
but the memory, configure, entities, and request-log routes resolve the caller
via `verify_auth` (`server/auth.py:145-161`) and then **discard the resolved
`User`**. Caller-supplied `user_id`/`agent_id`/`run_id` values are forwarded
straight to the memory backend, raw `memory_id` operations skip ownership
checks, and `/configure`/`/reset` accept any authenticated principal.

The report's source-level claims are accurate against the current HEAD. Every
cited line behaves as described.

## Threat model — what the report gets right, and what it under-weighs

**Correct:** the contract in the docs and the behavior in the code do not
match. The routes do not enforce a per-user scope, and `/configure`, `/reset`,
`/entities` accept any authenticated caller as if they were admins.

**Under-weighed by the report:** today only one `User` can exist with
`role = "admin"`. Migration `004_unique_admin_role.py` enforces this via a
partial unique index on `role = 'admin'`, and `/auth/register`
(`server/routers/auth.py:100-114`) is closed after the first user is
registered. There is **no public endpoint** to create non-admin users. The
Alice-vs-Bob attack sketch therefore cannot be constructed through the public
API as the code stands — the cross-tenant attack surface has exactly one
tenant.

The vulnerability is real but **latent**: it detonates the moment a second
`User` row appears, whether via a future invite endpoint (the docs at
`rest-api.mdx:267` already promise "additional accounts are provisioned by the
existing admin") or via direct database manipulation.

## Decision: scope B+ (admin-gate now, defer owner_id)

We fix the directly-fixable surface — global, destructive, and
info-disclosing routes — and align the docs with reality. We do **not** add
`owner_id` to memory payloads in this PR. The `owner_id` design needs the
multi-user invite UX to be specified first (admin/member/viewer? per-org?
hierarchical?), and JSONB payload schemas are very hard to back out once
vector stores carry production data. That work is tracked as a follow-up
issue.

Rejected alternatives:

- **A — Full multi-tenant now.** Premature schema commitment for an
  unspecified product feature. Violates KISS, locks us into payload shape we'd
  regret.
- **C — Doc-only (retract the multi-user promise).** Worse signal than "not
  yet"; the report's findings would remain "known limitation" rather than
  fixed.

## Authorization model

One new helper in `server/auth.py`:

```python
def _ensure_admin(request: Request, user: User | None) -> None:
    """Single source of truth for admin gating.
    Allows: legacy ADMIN_API_KEY env (X-API-Key), AUTH_DISABLED=true, or
    a registered User with role == 'admin'. Raises 403 otherwise."""
    auth_type = getattr(request.state, "auth_type", "none")
    if auth_type in {"admin_api_key", "disabled"}:
        return
    if user is not None and user.role == "admin":
        return
    raise HTTPException(status_code=403, detail="Admin role required.")


async def require_admin(
    request: Request,
    user: User | None = Depends(verify_auth),
) -> None:
    """FastAPI dependency. Pure gate — returns nothing."""
    _ensure_admin(request, user)
```

Properties:

- Pure gate: returns `None`, never invents a synthetic `User`.
- `_ensure_admin` is shared by the dep and by the inside-route guard on
  `GET /memories` (DRY).
- FastAPI dedupes the sub-dep, so `verify_auth` runs once per request.

## Regression matrix (current deployment modes × affected routes)

| Mode | What `verify_auth` returns today | After fix on admin-gated routes |
|---|---|---|
| Single admin JWT | admin `User` | passes (`role == "admin"`) |
| Single admin per-user key (`m0sk_…`) | admin `User` | passes (same) |
| Legacy `ADMIN_API_KEY` env (X-API-Key) | `None`, `auth_type="admin_api_key"` | passes (auth-type short-circuit) |
| `AUTH_DISABLED=true` | `None`, `auth_type="disabled"` | passes (auth-type short-circuit) |
| Hypothetical non-admin User | n/a (cannot exist today) | 403 |

**Zero behavior change on every supported deployment today.** The new 403 is
reachable only by a `User` type the current schema cannot produce.

## Per-route changes

### Full gate (`verify_auth` → `require_admin`)

| Route | File:line | Reason |
|---|---|---|
| `GET /configure` | `server/main.py:303-305` | Pairs with `POST /configure`; redacted config still exposes provider/topology to future non-admins |
| `POST /configure` | `server/main.py:313-318` | Global config mutation; **report-flagged** |
| `POST /reset` | `server/main.py:475-482` | Destructive global op; **report-flagged** |
| `GET /entities` | `server/routers/entities.py:44-68` | Info disclosure of every user/agent/run ID; **report-flagged** |
| `DELETE /entities/{type}/{id}` | `server/routers/entities.py:71-77` | Destructive global op masquerading as tenant action; **report-flagged** |
| `GET /requests` | `server/routers/requests.py:31-47` | Cross-user log leak the day a non-admin exists; **meta-reviewer-flagged** |

Mechanical change at each call site: replace `_auth=Depends(verify_auth)`
with `_admin=Depends(require_admin)`. In `requests.py`, drop the unused
`user: User = Depends(require_auth)` parameter.

### Inside-route guard (filtered branch unchanged)

`GET /memories` (`server/main.py:387-403`) — outer dep stays
`verify_auth`. Inside the route, on the no-filter branch (which currently
calls `_list_all_memories`), call `_ensure_admin(request, user)`. The
filtered branch (`?user_id=alice`) is untouched.

```python
@app.get("/memories", summary="Get memories")
def get_all_memories(
    request: Request,
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user: User | None = Depends(verify_auth),
):
    try:
        if not any([user_id, run_id, agent_id]):
            _ensure_admin(request, user)
            return _list_all_memories()
        filters = {
            k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items()
            if v is not None
        }
        return get_memory_instance().get_all(filters=filters)
    except Exception:
        raise upstream_error()
```

Rationale: full-gating the route would change behavior for the documented
per-user-key pattern (filtered queries). The inside-route guard only changes
the info-disclosure branch — the only branch the report's "list all" attack
uses.

### Deliberately NOT changed in this PR

| Route | Why |
|---|---|
| `POST /memories` | Real fix needs `owner_id` (follow-up) |
| `POST /search` | Same |
| `GET /memories/{memory_id}`, `PUT`, `DELETE`, `/history` | Same — ownership check requires `owner_id` |
| `DELETE /memories?user_id=…` (filtered branch) | Same |
| `POST /generate-instructions` | Rate-limit could regress batch callers; defer |
| `GET /configure/providers` | Static bundled-provider tuple; not sensitive, not flagged |
| `/api-keys/*`, `/auth/*` | Already scoped to caller via `require_auth` |

## Docs changes — `docs/open-source/features/rest-api.mdx`

Surgical line edits, no restructure:

1. **Line 134** (per-user API key row): rewrite to
   `Programmatic access tied to the single admin user today. Per-user
   scoping arrives with the upcoming multi-user invite flow.`
2. **Line 185** (`Per-user keys inherit the creating user's scope`):
   delete the sentence; it describes a contract the server does not enforce.
3. **Endpoint reference tables (lines 247-296):** add an `Admin only` marker
   to `/configure` (GET, POST), `/reset`, `/entities` (GET, DELETE), and
   `/requests`.
4. **Line 267**: keep "additional accounts are provisioned by the existing
   admin" but mark `(coming soon)` and remove any implication that today's
   per-user keys are already scoped.

## Tests — `server/tests/` (new)

`server/` currently has no pytest scaffolding. We add the minimum needed to
guard the regression matrix.

**New files:**

- `server/tests/__init__.py`
- `server/tests/conftest.py` — fixtures:
  - SQLite in-memory engine + session factory; bind `Base.metadata.create_all`.
  - `get_memory_instance` patched to return a `MagicMock` so memory routes
    don't need pgvector.
  - `client` fixture: FastAPI `TestClient` with the SQLite session injected
    via `app.dependency_overrides`.
  - `admin_user` fixture: inserts a `User(role="admin")` row and issues a JWT.
  - `non_admin_user` fixture: inserts a `User(role="member")` row (direct DB
    insert — no public endpoint produces this today) and issues a JWT.
  - `admin_api_key_env` and `auth_disabled_env` fixtures: monkey-patch the
    auth module to simulate those modes.
- `server/tests/test_admin_gating.py` — parametrized over the 6 admin-gated
  routes and the `GET /memories` no-filter branch:
  - admin JWT → expected success status (200/204)
  - admin per-user key → expected success
  - `ADMIN_API_KEY` env → expected success
  - `AUTH_DISABLED=true` → expected success
  - non-admin JWT → 403
  - no auth → 401
- `server/tests/test_unchanged_routes.py` — sanity coverage that filtered
  memory queries, `POST /memories`, `POST /search`, and `/api-keys/*` behave
  identically before/after.

**Dev dependencies** added to `server/requirements.txt` (or a new
`server/requirements-dev.txt`):

- `pytest`
- `pytest-asyncio`
- `httpx` (for `TestClient`)

**CI:** add a `server-ci.yml` workflow (model on `cli-python-ci.yml`) that
runs `pytest server/tests/` on PRs touching `server/`.

## Out of scope — tracked, not shipped

A single GitHub issue captures the deferred items. Each is one paragraph in
the issue body, not a separate design doc.

1. **`owner_id` on memory payloads.** Schema decision (payload key vs first-
   class column), backfill story for existing vector stores, SDK
   compatibility, write-path injection (`POST /memories`), read-path filter
   on every memory route, ownership check on `memory_id` operations.
2. **Multi-user invite flow.** UX (roles, per-org, hierarchies), endpoint
   surface (`POST /auth/invite`, `POST /auth/accept`), role transitions.
3. **Rate-limit `POST /generate-instructions`.** Gather usage data first;
   adding a limit could regress existing batch callers.
4. **Per-owner `GET /requests` filtering.** Requires `owner_id` on the
   `RequestLog` table.

## Backwards compatibility

- **No DB migration in this PR.**
- **No SDK changes**; request and response shapes are identical.
- **No environment variable changes.**
- **No breaking change** to existing single-admin deployments — every
  supported auth mode keeps working.

## Acceptance criteria

1. All five existing deployment modes (single-admin JWT, single-admin
   per-user key, `ADMIN_API_KEY` env, `AUTH_DISABLED=true`, plus authenticated
   non-admin which cannot exist today) succeed on every route they succeed
   on today.
2. The six admin-gated routes return 403 to a synthetic non-admin User
   (test-only DB insert).
3. `GET /memories` with no filter returns 403 to a synthetic non-admin;
   filtered calls are unchanged.
4. `ADMIN_API_KEY` and `AUTH_DISABLED` escape hatches are covered by
   automated tests, not just by code review.
5. `docs/open-source/features/rest-api.mdx` accurately describes the current
   per-user-key reality and marks the multi-user promise as "coming soon."
6. CI runs the new test suite on every PR touching `server/`.
7. Follow-up GitHub issue filed and linked from the PR description.

## Open questions for the implementation plan

- Test DB: SQLite in-memory vs SQLite file vs containerized Postgres? Default
  to in-memory unless `pgvector`-specific code paths are required (they
  aren't, given the `MagicMock` strategy).
- Should the new `server-ci.yml` workflow also run `ruff check`? (Likely
  yes — match the rest of the repo.)
- Whether to add a quick-start `make test` target in `server/Makefile`.
