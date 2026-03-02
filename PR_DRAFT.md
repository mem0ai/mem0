# PR Title: fix(embedchain): Lazy import optional Google dependencies in GmailLoader

## Description
This PR addresses a technical debt issue where `GmailLoader` was eagerly importing optional Google dependencies (`google-auth`, `googleapiclient`, etc.) at the module level. This caused `ImportError` when trying to use or test `GmailLoader` in environments where `embedchain[gmail]` was not installed.

Because of this eager import, `tests/loaders/test_gmail.py` was previously skipped with a "TODO".

## Changes
- **Lazy Imports**: Moved Google-related imports inside `_initialize_service` and `_get_credentials` methods in `embedchain/loaders/gmail.py`.
- **Enable Tests**: Removed `@pytest.mark.skip` from `tests/loaders/test_gmail.py`.
- **Fix Test Mocks**: Updated `test_gmail.py` to properly mock `GmailReader` (simulating the new lazy structure) and fixed a bug in the `BeautifulSoup` mock return value.

## Verification
- Ran `pytest tests/loaders/test_gmail.py` in a fresh environment *without* Google dependencies installed -> Successfully raises `ImportError` (as expected) or is handled gracefully if mocked.
- Ran the un-skipped tests with `pytest-mock` installed -> **Passed**.

## Checklist
- [x] I have read the [CONTRIBUTING](https://github.com/mem0ai/mem0/blob/main/CONTRIBUTING.md) document.
- [x] I have added tests to cover my changes.
- [x] All new and existing tests passed.
