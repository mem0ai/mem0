# Jonathan's Memory - SaaS MVP Status

This document tracks the progress of converting OpenMemory into a multi-tenant SaaS application ("Jonathan's Memory") with Supabase authentication.

## Overall Goal
Launch a functional multi-tenant Minimum Viable Product (MVP) with:
1.  User authentication (Supabase).
2.  User-scoped memory storage and retrieval.
3.  Deployment to a simple cloud platform (future phase).

## Current Phase: Frontend Integration - Debugging Connection & CORS

### Completed Steps (Backend Authentication & Multi-Tenancy):
*   **Branch Creation:** Active development on `feat/supabase-auth-multitenancy`.
*   **Dependencies:** `supabase` package correctly configured in `requirements.txt`.
*   **Environment Configuration:** `.env` setup for Supabase, Qdrant, OpenAI, and `mem0` settings.
*   **Core Authentication (`app/auth.py`, `main.py`):** Supabase client initialized; `get_current_supa_user` FastAPI dependency implemented and applied to routers.
*   **`mem0` Client (`app/utils/memory.py`):** Configured for a static shared Qdrant collection.
*   **Database Utilities (`app/utils/db.py`):** `get_or_create_user()` and `get_user_and_app()` adapted for Supabase User IDs.
*   **Routers Adapted (`memories.py`, `apps.py`, `stats.py`):** Endpoints refactored for Supabase JWT authentication.
*   **MCP Server (`app/mcp_server.py`):** Adapted for Supabase User ID.
*   **Database Initialization:** Alembic migrations run.
*   **API Startup & Basic Multi-Tenancy Tests:** Backend API starts; initial tests showed data isolation for `useMemoriesApi.ts` after manual login. **Further testing confirmed memory creation and app listing are functional after backend fixes.**
*   **Docker Environment:** Successfully configured Dockerfiles and `.env` handling for both UI and API services. `docker compose build` and `docker compose up -d` are now stable.
*   **Backend Error Resolution:**
    *   Fixed `AttributeError: 'Query' object has no attribute 'scalar_one'` in `app/routers/apps.py`.
    *   Resolved `UNIQUE constraint failed: apps.name` by modifying `App` model schema (composite unique key `(owner_id, name)`) and applying Alembic migration. Core multi-tenancy for app ownership is now correctly handled.

### Frontend Integration Progress:
*   **Supabase Client & AuthContext:** `supabaseClient.ts` and `AuthContext.tsx` (with `"use client;"`) created. `AuthContext` manages session and provides a global JWT accessor (`getGlobalAccessToken`).
*   **`apiClient.ts`:** Axios instance configured with an interceptor to use `getGlobalAccessToken` for attaching JWTs.
*   **Custom Hooks Updated:** `useMemoriesApi.ts`, `useFiltersApi.ts`, `useAppsApi.ts`, `useStats.ts` have been modified to use `apiClient`.
*   **Auth UI:** Basic `AuthForm.tsx` and `LogoutButton.tsx` created; `AuthProvider` wraps `app/layout.tsx`.
*   **Dependency Management:** Switched to `pnpm` for frontend dependencies.

### Next Phase: Resolve Runtime Errors & Complete Frontend - Backend Integration

**[STATUS UPDATE: Major backend/Docker blockers resolved. Core functionality (auth, memory creation, app listing) is working. Frontend refinements (Redux user_id, AuthForm style, Logout) implemented. Final verification pending.]**

**Immediate Next Steps:**

1.  **~~Stabilize Backend API Service & CORS for POST/PUT/DELETE:~~ [DONE]**
    *   Docker environment (UI and API) builds and runs successfully. Backend errors causing 500s (and thus CORS-like symptoms) have been resolved.
    *   API is running, accessible, and core operations succeed with JWT auth.

2.  **Verify All Frontend API Calls: [LARGELY DONE - CORE FUNCTIONALITY WORKING - PENDING FINAL TEST]**
    *   Rely on `docker compose up -d --build` for full stack testing.
    *   **Verification mostly COMPLETE for:**
        *   Console logs show `AuthContext: globalAccessToken updated: <VALID_JWT>`.
        *   API calls use `Authorization: Bearer <JWT>` header.
        *   Memory creation and app listing now return 2xx.
    *   **Recent Fixes to Verify:**
        *   Confirm Redux `state.profile.userId` now correctly reflects the Supabase user ID in logs and subsequent API calls.
        *   Confirm no 401 errors from hooks attempting to fetch data immediately after logout.
        *   Confirm logout redirects to `/auth`.
        *   Confirm AuthForm styling and Google Sign-In button presence.

3.  **Improve Login UX: [DONE]**
    *   Navbar now shows conditional Login/Logout buttons. AuthForm styling improved.

4.  **Synchronize Redux `user_id`: [DONE]**
    *   `AuthContext.tsx` now dispatches `setUserId` with Supabase user ID.
    *   `profileSlice.ts` updated to handle `null` and initialize `userId` to `null`.
    *   Data fetching hooks (`useFiltersApi`, `useAppsApi`, `useMemoriesApi`, `useStats`) now have guards to prevent API calls if `user_id` is null.

### Key Outstanding Issues & Questions (Post-MVP or in Parallel with above debugging):
*   **~~Original `user_id=deshraj` Source:~~ [RESOLVED]** This was due to Redux `initialState` and lack of update from Supabase auth. Now fixed.
*   **Pydantic V2 Migration:** (From original plan) Address deprecation warnings for Pydantic V1 style models.
*   **SSE Endpoint Security (`mcp_server.py`):** (From original plan) Needs robust JWT authentication.
*   **`check_memory_access_permissions` Review:** (From original plan) Adapt for complex scenarios if needed.

---
*(This file will be updated as progress is made.)* 