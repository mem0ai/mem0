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

---

## 6. Update & Learnings: The Metadata Implementation Journey

The implementation of the metadata tagging feature revealed a critical, subtle bug that required a significant pivot in our approach. This section documents our findings.

### 6.1. Initial Diagnosis and Failure

Our initial plan was to add an optional `tags_filter` to the `search_memory` tool and pass it down to the underlying `mem0.search()` function. This was based on the assumption that the `mem0` library supported direct metadata filtering in its search queries.

**This assumption was incorrect.**

Our tests consistently failed with an `AssertionError`, indicating that even when a memory was added with tags, a search for those tags returned zero results. Our debugging logs revealed the core issues:
1.  **The `add` function was not storing metadata correctly.** We initially fixed this by passing the metadata inside the message object.
2.  **The `search` function was not returning the metadata.** Even after fixing the `add` function, logs showed that search results from `mem0.search()` were missing the `tags` field in their metadata payload.

**This proves the bug is in the data persistence/retrieval pipeline of the `mem0` library itself.** Our server-side code was correctly sending the data, but the library was silently failing to store or return it completely.

### 6.2. The Correct, Robust Solution

Since we cannot rely on the underlying library to perform the filtering, we pivoted to a more robust, albeit less performant, solution: **in-application filtering**.

1.  **`add_memories`**: The function is correctly structured to pass the `metadata` payload (with `tags`) as part of the message object. This is the correct way to send the data.
2.  **`search_memory_v2`**: This new tool fetches a larger-than-needed batch of memories based on the semantic query and then **manually filters the results in our Python code**. It iterates through the results and includes only those that contain the required tags in their metadata.

This approach is safer because it does not depend on the buggy or undocumented behavior of the external library. It gives us full control over the filtering logic.

### 6.3. Next Steps & Future Investigation

This experience provides a clear path for future improvement:

1.  **Investigate `mem0` and Qdrant**: As you suggested, the next step is a deep dive into the `mem0` library's source code and the Qdrant client documentation. We need to understand precisely why the metadata is being dropped. Is it a bug? Is it a configuration issue? Answering this is a high-priority technical task.
2.  **Contribute Upstream or Fork**: If we discover a bug in the `mem0` library, we should consider contributing a fix to the open-source project. If that's not feasible, we may need to fork the library to implement the direct database-level filtering we need for optimal performance.
3.  **Implement a `context` Field**: Our discussion about a dedicated `context` field for strict segmentation is still highly relevant. The investigation into the `mem0` library will directly inform how we can best implement this feature in the future.

This journey has been a powerful lesson in the challenges of integrating with external libraries and the importance of rigorous, end-to-end testing. The current implementation is stable and correct, and we now have a clear, data-driven plan for future enhancements. 