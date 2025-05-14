# Jonathan's Memory: SaaS Conversion Plan

This document outlines the high-level plan to convert the open-source OpenMemory project into a multi-tenant SaaS application, "Jonathan's Memory," leveraging insights from the "jean-memory" project for simplicity and robustness, especially in authentication.

## Phase 0: Stabilize Local OpenMemory Instance

**Goal:** Achieve a consistently stable and functional local deployment of the current OpenMemory project. This is a critical prerequisite.

**Tasks:**
1.  **Resolve OpenAI API Key Issues:**
    *   Ensure `openmemory/api/.env` correctly provides `OPENAI_API_KEY`.
    *   Verify the API key is valid, has billing enabled, and permissions for all required OpenAI models (chat and embeddings).
    *   Thoroughly test memory creation, retrieval, and search locally to ensure no `401 Unauthorized` errors persist.
2.  **Address Container Instability:**
    *   Investigate and resolve `exit code 137` (OOMKill) for the `openmemory-mcp-1` container. This may involve:
        *   Increasing Docker's allocated memory.
        *   Optimizing the application if it's inefficient.
    *   Ensure all Docker services (`openmemory-mcp`, `openmemory-ui`, `mem0_store`) run reliably without unexpected exits.
3.  **Confirm Core Functionality:** Ensure all basic OpenMemory features work as expected in a local environment connected to Claude.

## Phase 1: MVP - Authentication and User-Scoped Memory

**Goal:** Implement basic user authentication and ensure that each user's memories are isolated.

**Key Technologies:**
*   **Authentication:** Supabase Auth (recommended for simplicity and your familiarity).
*   **Backend:** Python/FastAPI (modifying existing OpenMemory backend).
*   **Database (User Data):** Supabase's integrated PostgreSQL for user profiles, API keys (if users bring their own LLM keys in the future), and other metadata.
*   **Vector Store (Multi-tenancy):** Qdrant (as currently used by OpenMemory).

**Tasks:**
1.  **Authentication Setup (Supabase):**
    *   Set up a Supabase project.
    *   Integrate Supabase for user registration (email/password, potentially Google OAuth later).
    *   Implement login/logout functionality.
2.  **Backend API Modifications (FastAPI):**
    *   Add authentication middleware to FastAPI to protect endpoints. (e.g., using JWTs provided by Supabase).
    *   Modify existing API endpoints (memory creation, retrieval, search, etc.) to be user-aware. All operations must be scoped to the authenticated user's data.
    *   Create new endpoints for user management if needed (e.g., fetching user profile).
3.  **Multi-Tenancy for Qdrant:**
    *   **Strategy:** Create a separate Qdrant collection per user (e.g., `memories_user_<user_id>`).
    *   **Implementation:** Modify the backend logic to dynamically use the correct Qdrant collection based on the authenticated user's ID. This ensures strong data isolation.
4.  **Frontend Integration (React/Next.js):**
    *   Add login, registration, and logout pages/components to the `openmemory/ui/`.
    *   Implement logic to handle user sessions (e.g., storing JWTs securely).
    *   Ensure API calls from the frontend include the authentication token.
    *   Display user-specific information.
5.  **Configuration:**
    *   Manage Supabase URL and service key securely in the backend environment (`openmemory/api/.env`).

## Phase 2: Basic Cloud Deployment

**Goal:** Deploy the MVP to a simple cloud environment.

**Tasks:**
1.  **Container Review:** Ensure Dockerfiles for backend and frontend are optimized for production.
2.  **Cloud Provider Choice:** Select a cloud provider (e.g., DigitalOcean, Render, Railway, or a more comprehensive one like AWS/GCP if you're comfortable).
3.  **Deployment Strategy:**
    *   **Backend & Frontend:** Deploy as containerized applications. Services like Render, Railway, or Google Cloud Run can simplify this.
    *   **Qdrant:** Either deploy Qdrant as another container alongside your application or use a managed Qdrant cloud service if available and preferred.
    *   **Supabase:** Continue using Supabase for Auth and PostgreSQL.
4.  **Environment Configuration:** Set up production environment variables securely in the chosen cloud platform.
5.  **Domain & Basic DNS:** Configure a domain for your application.

## Phase 3: Rebranding and Initial Polish

**Goal:** Rename the application to "Jonathan's Memory" and apply initial branding.

**Tasks:**
1.  **Frontend Text & Asset Changes:**
    *   Search and replace "OpenMemory" and related terms with "Jonathan's Memory" throughout the `openmemory/ui/` codebase.
    *   Update logos, favicons, and other visual assets.
2.  **Basic UI/UX Improvements:** Address any glaring UI issues for a smoother initial user experience.
3.  **Documentation/Onboarding:** Create simple instructions for users.

## Future Enhancements (Post-MVP)

*   Advanced user management features.
*   Subscription/Billing integration.
*   Support for users bringing their own LLM API keys.
*   More sophisticated context source integrations.
*   Admin dashboard.
*   Scalability and performance optimizations.
*   Enhanced security measures.

## Timeline & Effort Estimation (Very Rough):

*   **Phase 0 (Stabilization):** 1-3 days (highly dependent on the root cause of current local issues). *This must be completed first.*
*   **Phase 1 (MVP - Auth & Scoping):** 2-4 weeks (assuming familiarity with FastAPI, React, and Supabase). This involves significant backend re-architecting for multi-tenancy.
*   **Phase 2 (Basic Cloud Deployment):** 1-2 weeks.
*   **Phase 3 (Rebranding):** 3-5 days.

**Total for a simple, deployed MVP: Potentially 4-7 weeks AFTER local stabilization.** Getting a robust, consumer-ready product will take significantly longer. Setting this up "today or tomorrow" for the full SaaS vision is not realistic, but making progress on Phase 0 and refining this plan is achievable.

## Key Considerations from "jean-memory":

*   **Authentication Simplicity:** "jean-memory" used Google OAuth. Supabase can provide this and also simpler email/password auth, which might be a good starting point for "Jonathan's Memory."
*   **Backend Structure:** The FastAPI structure in "jean-memory" ([https://github.com/jonathan-politzki/jean-memory](https://github.com/jonathan-politzki/jean-memory)) can serve as a good reference for organizing routes and services.
*   **Environment Variables:** Adopt a clear and consistent approach for managing environment variables, similar to `jean-memory/.env.example`.

---

This plan provides a roadmap. The immediate next step is to ensure your local OpenMemory instance is stable. 