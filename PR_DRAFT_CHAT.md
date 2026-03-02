# PR Title: feat(rest-api): Enable /chat endpoint with session_id support

## Description
The REST API example (`embedchain/examples/rest-api`) had the `/chat` endpoint commented out with a `FIXME`. This feature is essential for users wanting to build stateful chat applications using the REST interface.

The issue was likely due to the lack of `session_id` in the request model, which is required for `App.chat()` to maintain conversation history.

## Changes
- **Updated `MessageApp` model**: Added `session_id` field (defaulting to "default").
- **Enabled `/chat` endpoint**: Uncommented the endpoint in `main.py` and wired it to call `app.chat(body.message, session_id=body.session_id)`.

## Verification
- Validated via `fastapi.testclient`:
    - Verified that POST `/chat` with `session_id` correctly calls `App.chat` with the session identifier.
    - Confirmed response handling.

## Checklist
- [x] I have read the [CONTRIBUTING](https://github.com/mem0ai/mem0/blob/main/CONTRIBUTING.md) document.
- [x] Tested locally with `TestClient`.
