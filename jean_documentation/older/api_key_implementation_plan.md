# Blueprint: Implementing API Key Authentication for MCP

This document outlines the engineering plan to implement a robust, secure, and user-friendly API key system for agent authentication. This will provide a superior developer experience, allowing any third-party agent to establish a durable, persistent connection to the Jean Memory service.

---

## 1. Backend Implementation

The foundation of this system is the ability to securely generate, store, and validate API keys.

### 1.1 Database Schema (`openmemory/api/app/models.py`)

-   **Create a new `ApiKey` table:**
    -   `id`: Standard primary key.
    -   `key`: A securely generated, unique string. This is the secret key shown to the user. We must store a **hashed version** of this key, never the key itself.
    -   `user_id`: A foreign key linking to the `User` table.
    -   `name`: A user-provided name for the key (e.g., "My Personal Agent").
    -   `created_at`: Timestamp for when the key was generated.
    -   `last_used_at`: Timestamp to track key activity. (Optional but good for auditing).
    -   `is_active`: A boolean to allow for revoking keys.

### 1.2 API Endpoints (`openmemory/api/app/routers/keys.py`)

-   **`POST /api/v1/keys`**:
    -   **Action:** Creates a new API key for the currently authenticated user.
    -   **Input:** `{ "name": "A descriptive name" }`
    -   **Process:**
        1.  Generate a secure, random key string (e.g., `jean_sk_...`).
        2.  Hash the key using a strong, one-way algorithm (e.g., SHA-256).
        3.  Store the hashed key and other details in the new `ApiKey` table.
        4.  Return the **unhashed, plaintext key** to the user **one time only**.
    -   **Security:** This endpoint must be protected and require a valid user session (JWT).

-   **`GET /api/v1/keys`**:
    -   **Action:** Lists all of the user's existing API keys (without revealing the secret key itself).
    -   **Output:** An array of objects, e.g., `[{ "id": "...", "name": "...", "created_at": "..." }]`.

-   **`DELETE /api/v1/keys/{key_id}`**:
    -   **Action:** Revokes an API key by setting `is_active = false`.
    -   **Security:** Must verify that the key being deleted belongs to the authenticated user.

### 1.3 Update MCP Authentication (`openmemory/api/app/mcp_server.py`)

-   **Modify `handle_sse_connection`:**
    1.  The client will present the API key in the `Authorization: Bearer <API_KEY>` header.
    2.  The server will receive the key.
    3.  It will hash the received key using the same algorithm.
    4.  It will query the `ApiKey` table for a matching hash.
    5.  If a match is found for an active key, the connection is validated for the associated `user_id`.
    6.  If no match is found, the connection is rejected with a `401 Unauthorized` error.

---

## 2. Frontend Implementation

The user needs a simple interface to manage their keys.

### 2.1 Settings Page (`openmemory/ui/app/settings/page.tsx` or similar)

-   **Create a new "API Keys" section.**
-   **Display existing keys:** Show a list of the user's keys (name, creation date, etc.) fetched from the `GET /api/v1/keys` endpoint.
-   **"Generate New Key" button:**
    -   Presents a dialog asking for a key name.
    -   Calls the `POST /api/v1/keys` endpoint.
    -   Displays the newly generated key in a modal with a "Copy" button.
    -   Includes a strong warning that this is the only time the key will be shown.
-   **"Revoke" button:**
    -   Associated with each key in the list.
    -   Calls the `DELETE /api/v1/keys/{key_id}` endpoint to disable the key.

---

## 3. Documentation Overhaul (`openmemory/ui/app/mcp-docs/page.tsx`)

Once the above is implemented, we will create the definitive documentation.

-   **Layout:** A minimalist, professional two-column layout with a sidebar.
-   **Content:**
    -   **Authentication:** A clear guide showing the user how to navigate to the settings page, generate a new API key, and copy it.
    -   **Integration:** A full, runnable Python script that shows the developer how to:
        1.  Load the API key from an environment variable (`JEAN_API_TOKEN`).
        2.  Use the `mcp` Python SDK.
        3.  Connect to their personalized MCP endpoint URL, passing the API key in the header for the initial handshake.
        4.  Establish a durable connection and call the memory tools.
    -   **Clarity:** The documentation will explicitly state that this API key method is the **official, recommended way** for all custom agents to connect. 