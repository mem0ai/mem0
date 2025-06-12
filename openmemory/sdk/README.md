# Jean Memory Agent API & SDK

This document provides a complete overview of the Jean Memory Agent API, its Python SDK, and the path to deploying it in a production environment. It is intended for the developer who will be taking this project forward.

## 1. Goal & Current Status

**Objective:** To create a robust, secure, and isolated REST API for AI agent swarms, allowing external businesses (like Koii) to use Jean Memory without interfering with existing tools.

**Current Status:** **Complete and Ready for Production Deployment.**
-   The new Agent API is built and located in `openmemory/api/app/agent_api.py`.
-   It is **architecturally isolated**, as detailed in the [Architecture Guide](./architecture.md).
-   It is **feature-flagged** and will remain dormant in production until the `ENABLE_AGENT_API` environment variable is set to `true`.
-   This SDK (`client.py`) provides a simple interface for developers.
-   A comprehensive test suite (`examples/test_jean_memory_api.py`) and a branded CLI (`jean_memory_cli.py`) have been created to validate all functionality.
-   The production-like Docker environment is running successfully with the new code.

## 2. Documentation

This SDK comes with a full set of documentation:
-   **[API Reference](./api_reference.md):** Detailed information on authentication, endpoints, and request/response schemas.
-   **[API Cookbook](./api_cookbook.md):** Advanced, real-world examples for complex agentic workflows.
-   **[Architecture Guide](./architecture.md):** A high-level diagram illustrating the system's isolated design.

## 2. How to Use and Test

The new system is designed to be easy to test and use.

### Running the Test Suite

A branded Command-Line Interface has been created to simplify testing. From the project root, you can run the full test suite:

```bash
# Set your keys in the environment
export JEAN_API_TOKEN="<your_auth_token_or_dummy_token>"
export OPENAI_API_KEY="<your_openai_key>"

# Run all tests
python3 jean_memory_cli.py test
```

You can also run specific tests using pytest's `-k` flag:
```bash
# Run only the basic add-and-search test
python3 jean_memory_cli.py test -k "add_and_search"

# Run only the LLM-driven collaboration test
python3 jean_memory_cli.py test -k "collaboration"
```

### Using the Python SDK

The `JeanMemoryClient` is the primary interface for developers.

```python
from openmemory.sdk.client import JeanMemoryClient

# The client uses the production URL by default and reads JEAN_API_TOKEN from the environment
client = JeanMemoryClient()

# Add a tagged memory for a specific client application
client.add_tagged_memory(
    text="This is a memory for the Koii project.",
    metadata={"task_id": "koii_task_123", "type": "log"},
    client_name="koii_swarm_app"
)

# Search for memories specific to that task
memories = client.search_by_tags(
    filters={"task_id": "koii_task_123"},
    client_name="koii_swarm_app"
)
```

## 3. Key Learnings & Production Guidance

The development process revealed several important insights for managing this codebase.

*   **Database Schema is King:** We encountered an error (`column users.is_anonymous does not exist`) because the code temporarily diverged from the production database schema. **The final code is now correctly aligned with the production schema.** For any *future* database changes, the correct process is to:
    1.  Update the model in `openmemory/api/app/models.py`.
    2.  Run `alembic revision --autogenerate -m "Your descriptive message"` to create a migration script.
    3.  Run `alembic upgrade head` to apply the change to the database.
    This was not needed for this project, as we reverted the code to match the existing schema.

*   **Environment Consistency:** The server must be run with a Python version that matches the one used to install dependencies. The `Dockerfile` handles this correctly for the production environment.

*   **Concurrency:** The `agent_api.py` includes a `threading.Lock` around database writes. This is to make local testing against SQLite reliable. It is safe for production, as a production-grade database like PostgreSQL handles concurrency automatically and this lock will have no negative impact.

## 4. Path to Production

The API is ready for deployment. Here are the recommended steps:

1.  **Code Review:** Review the new files:
    *   `openmemory/api/app/agent_api.py`
    *   `openmemory/sdk/client.py`
    *   `examples/test_jean_memory_api.py`
    *   `jean_memory_cli.py`
    *   And the changes to `openmemory/api/main.py`.

2.  **Deploy to Render:** Deploy the code to your production Render environment. The new Agent API **will not be active** by default.

3.  **Enable the Feature Flag:** In your Render environment settings, add the following environment variable:
    *   `ENABLE_AGENT_API=true`

4.  **Issue Client Tokens:** Provide your business clients (like Koii) with a `JEAN_API_TOKEN` (JWT token) so they can authenticate with the API.

5.  **Provide Documentation:** Share the `api_reference.md` and `api_cookbook.md` files from the `build_docs` directory with your clients.

This completes the handoff. The system is stable, tested, and ready for the next steps. 