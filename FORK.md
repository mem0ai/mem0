# 🚀 OpenMemory - A local first OpenAI Memory Model

**Maintained by @garciaba79**

---

This fork is a hardened version of `mem0/openmemory`, specifically refactored to support robust, local-only deployments. It addresses several "cloud-first" biases in the original code where settings were hardcoded or ignored.

### 🛠️ Key Architectural Improvements
* **Database: SQLite to Postgres Migration**
    * Replaced the default SQLite persistence with **Postgres** for enterprise-grade reliability and concurrency.
* **Dynamic Model Logic**
    * Patched the codebase to stop ignoring `OPENAI_BASE_URL`.
    * The application now strictly respects environment variables for Local LLMs (LM Studio/Ollama) instead of falling back to hardcoded cloud strings.
* **Persistence Fixes**
    * **Settings Page Fix**: Resolved a critical bug where the UI "Settings" page failed to save changes to the database.
    * **CORS Policy**: Adjusted origin settings to allow local cross-service communication without browser blocks.

### ⚙️ Environment & DevOps
* **Docker Compose Refactor**: 
    * Centralized all configuration into `docker-compose.yml` for a "Single Source of Truth."
    * Improved volume mapping and networking for local PC environments.
* **Inference Tuning**: 
    * Optimized `max_tokens` and updated inference defaults to suit local GPU/CPU hardware.
    * Removed non-functional/unsupported prompt variables from the upstream source.

### 📂 Project Cleanup
* Standardized the directory structure by moving diagnostic tests to a dedicated `/test` folder.
* Removed orphaned pipeline files to keep the core memory engine lean.