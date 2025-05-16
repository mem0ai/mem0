# Jonathan's Memory - SaaS MVP Status

This document tracks the progress of converting OpenMemory into a multi-tenant SaaS application ("Jonathan's Memory") with Supabase authentication.

## Overall Goal
Launch a functional multi-tenant Minimum Viable Product (MVP) with:
1.  User authentication (Supabase).
2.  User-scoped memory storage and retrieval.
3.  Deployment to a simple cloud platform (future phase).

## Current Phase: Backend - Authentication & Multi-Tenancy Implementation

### Completed Steps:
*   **Branch Creation:** User confirmed new Git branch `feat/supabase-auth-multitenancy` is active.
*   **Dependencies:**
    *   Added `supabase-py` to `openmemory/api/requirements.txt` (User corrected to `supabase`).
    *   Corrected `mem0ai` version in `openmemory/api/requirements.txt` to an available one (`>=0.1.92,<0.2.0`) after Docker build failure.
*   **Environment Configuration:**
    *   User provided with a template for `openmemory/api/.env` including Supabase URL, ANON_KEY (user to add SERVICE_KEY), Qdrant, OpenAI, and `mem0` settings.
    *   Plan created for updating `openmemory/api/.env.example`. (User to confirm `.env` is populated with actual secrets).
*   **Core Authentication (`openmemory/api/main.py`):**
    *   Supabase client initialization and `get_current_supa_user` moved to `openmemory/api/app/auth.py` to resolve circular imports.
    *   Routers (memories, apps, stats) updated to use `get_current_supa_user` from `app.auth`.
    *   Old default user/app logic removed/commented out.
*   **`mem0` Client (`openmemory/api/app/utils/memory.py`):**
    *   `get_memory_client()` revised to configure `mem0` with a static, shared Qdrant collection name (`MAIN_QDRANT_COLLECTION_NAME`) and necessary API keys from environment variables.
*   **Database Utilities (`openmemory/api/app/utils/db.py`):**
    *   `get_or_create_user()` and `get_user_and_app()` adapted to use Supabase User ID (string UUID) for querying/creating local `User` records (mapping Supabase ID to `User.id` PK and `User.user_id` string field).
*   **Routers Adapted for Auth & User Scoping:**
    *   `openmemory/api/app/routers/memories.py`: Endpoints updated. Corrected `get_current_supa_user` import path to `app.auth`. Corrected `SupabaseUser` type hint import.
    *   `openmemory/api/app/routers/apps.py`: Endpoints updated. Corrected `get_current_supa_user` import path to `app.auth`. Corrected `SupabaseUser` type hint import. Corrected `SyntaxError` in `list_apps` subquery chaining.
    *   `openmemory/api/app/routers/stats.py`: Endpoint updated. Corrected `get_current_supa_user` import path to `app.auth`. Corrected `SupabaseUser` type hint import.
*   **MCP Server (`openmemory/api/app/mcp_server.py`):**
    *   Tools (`add_memories`, `search_memory`, etc.) updated to use Supabase User ID from context for `mem0` calls and database interactions.
    *   Relies on `mem0`'s `user_id` parameter for data isolation in the shared Qdrant collection.
    *   Security note added for SSE endpoint authentication.

### Next Immediate Steps:
1.  **Populate `.env`:** Ensure `openmemory/api/.env` is correctly populated with actual secrets (Supabase service key, OpenAI key).
2.  **Build & Run Backend:**
    *   User to ensure `requirements.txt` uses correct `supabase` package name and `mem0ai` version.
    *   Run `docker compose build openmemory-mcp` (expected to succeed with corrected syntax in `apps_router.py`).
    *   Run `docker compose up -d openmemory-mcp mem0_store`.
    *   Check logs for startup errors (`docker compose logs openmemory-mcp`).
3.  **Initial API Testing (Manual):**
    *   Test user creation/login via Supabase (externally, e.g., using Supabase UI or a simple script) to obtain JWTs.
    *   Test protected API endpoints with and without JWTs.
    *   Test core memory operations (create, list, get, delete) for multiple users to verify data isolation.
4.  **Address Linter Errors in `apps_router.py`**: Investigate and fix the persistent linter errors.
5.  **Review & Address Outstanding Issues.**

### Key Outstanding Issues & Questions to Address:
*   **`apps_router.py` Linter Errors**: Resolved `SyntaxError`. Linter may still show cosmetic warnings on some lines but should not be a blocking syntax issue.
*   **SSE Endpoint Security (`mcp_server.py`)**: `handle_sse` endpoint needs JWT authentication.
*   **Missing Routers**: `users_router.py`, `feedback_router.py` (imported in `main.py` but not found).
*   **Alembic Migrations for `User` Table**: Confirm if schema changes or constraints on `User.user_id` require a migration.
*   **`check_memory_access_permissions` Function**: Review and adapt this function in `memories_router.py`.
*   **`mem0` Multi-Tenancy Behavior**: Verify `mem0`'s payload filtering for user isolation in Qdrant.
*   **Email in MCP Context**: `get_user_and_app` called with `email=None` in MCP tools.
*   **SQL `Memory` and `mem0_id` Linking**: Consider making `mem0_id` a dedicated column in the `Memory` table.

---
*(This file will be updated as progress is made.)* 