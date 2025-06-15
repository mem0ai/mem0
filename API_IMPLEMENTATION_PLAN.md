# API Implementation Plan: Secure, Programmatic Tool Access

## 1. Objective

To implement a secure, non-breaking, programmatic API that allows developers to execute memory tools using an API key. This will be achieved by creating a unified, stateless endpoint that serves both existing integrations (like Claude) and new API users, without requiring any changes to existing client configurations.

---

## 2. Core Problem & Diagnosis

Our recent attempts have been plagued by a recurring startup error:

```
AttributeError: 'FastMCP' object has no attribute 'tools'. Did you mean: 'tool'?
```

**This error was my fault.** It stems from an incorrect assumption I made about the `mcp.server` library.

-   **Incorrect Assumption**: I tried to dynamically create a `tool_registry` by accessing a `mcp.tools` attribute.
-   **Root Cause**: The `FastMCP` library does **not** expose a public `.tools` collection. The correct and intended pattern, as seen in your original codebase, is to **manually define a dictionary** that maps tool name strings to their corresponding functions.

This fundamental error caused the repeated build failures. We will now proceed with the correct pattern.

---

## 3. Architectural Principles (Our North Star)

This plan adheres to the principles discovered in the project's architecture documents (`INTEGRATION_ARCHITECTURE.md`) and your own correct instincts.

-   **✅ Unified MCP Endpoint**: We will use a single, stateless `POST /mcp/messages/` endpoint to handle all tool executions. This maintains a clean and consistent architecture.
-   **✅ Zero Breaking Changes**: This endpoint will feature a **dual-path authentication** mechanism to support both old and new clients simultaneously.
    -   **Path A (Existing Clients)**: Requests from the Cloudflare Worker/Claude will continue to use `x-user-id` and `x-client-name` headers. The system will work for them exactly as it does now.
    -   **Path B (New API Users)**: Requests from developers will use an `X-Api-Key` header for authentication.
-   **✅ Clean & Decoupled**: The logic will be self-contained within the API layer, requiring no complex routing or feature flags.

---

## 4. The Blueprint: Implementation Steps

We will systematically clean the codebase and implement the correct logic.

### Step 0: Clean the Workspace

To ensure we have a clean slate, we must first remove the artifacts from our previous failed attempts.

1.  **Delete New File**: Delete `openmemory/api/app/mcp_server_new.py`.
2.  **Delete New Router**: Delete `openmemory/api/app/routers/agent_api.py`.
3.  **Revert Main**: Revert `openmemory/api/main.py` to its original state, removing the imports for the now-deleted files.

### Step 1: Fix `openmemory/api/app/mcp_server.py` (The Core Bugfix)

This is the most critical step. We will correct the file to properly handle tool registration and requests.

1.  **Fix the `AttributeError`**:
    -   Remove the incorrect line: `tool_registry = {tool.name: tool.fn for tool in mcp.tools.values()}`.
    -   **Manually create the `tool_registry` dictionary**. This dictionary will explicitly map the string name of each tool to its function object (e.g., `"add_memories": add_memories`).

2.  **Implement the Unified Endpoint**:
    -   Ensure the `handle_post_message` function (the one you originally wrote) is present.
    -   This function will contain the dual-path authentication logic: check for an authenticated user on `request.state`, and if not present, fall back to checking for `x-user-id` headers.
    -   It will use the manual `tool_registry` to look up and execute the requested tool.

3.  **Preserve SSE Handlers**:
    -   The existing `handle_sse_connection` and `handle_sse_messages` endpoints for local development will be left completely untouched.

### Step 2: Correct `openmemory/api/app/auth.py`

The authentication dependency needs one final polish to work cleanly with the unified endpoint.

1.  **Modify `get_user_from_api_key_header`**:
    -   This function will accept `request: Request` as an argument.
    -   After successfully validating the `X-Api-Key` and fetching the `user`, it will attach the user object to the request's state: `request.state.user = user`.
    -   It will **not** be responsible for routing or calling other functions. Its only job is to authenticate and attach the user to the request.

### Step 3: Finalize `openmemory/api/main.py`

The main application file should be simplified.

1.  **Remove `agent_api_router`**: The logic is now consolidated in `mcp_server.py`, so the separate agent router is no longer needed.
2.  **Remove Feature Flag**: The `ENABLE_AGENT_API` environment variable is no longer necessary, as the new implementation is safely integrated.

---

## 5. Testing & Validation

Once these changes are implemented, the server will build successfully. You can then test the API key flow using the unified endpoint.

**Test Command:**

```bash
curl -X POST http://localhost:8765/mcp/messages/ \
-H "Content-Type: application/json" \
-H "X-Api-Key: <YOUR_API_KEY_HERE>" \
-d '{
  "method": "ask_memory",
  "params": {
    "question": "what is the last thing I told you to remember?"
  }
}'
```

This plan provides a clear, correct, and non-breaking path to achieving our goal. It is based on your own sound architectural ideas, and I am confident it will succeed. 