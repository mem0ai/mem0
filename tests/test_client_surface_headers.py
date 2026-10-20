"""Surface-identity headers, and that a client can be constructed at all.

The construction test exists because it was not there: a signature change to
_bounded_stack missed the _client_stack call site, every MemoryClient(...) raised
TypeError, and the whole suite stayed green because nothing built one.
"""

import os
from unittest.mock import patch

from mem0.client.main import _bounded_stack, _client_headers, _client_stack


def test_a_client_can_be_constructed():
    from mem0 import MemoryClient

    # _validate_api_key normally populates org/project from the API response;
    # stubbing it leaves them None, which a later accessor rejects. Set them the
    # way a real validation would. This test is about construction reaching the
    # header stage at all.
    def _stub(self):
        self.org_id, self.project_id = "org", "proj"

    with patch.object(MemoryClient, "_validate_api_key", _stub):
        client = MemoryClient(api_key="m0-test")

    assert client.client.headers["X-Mem0-Client"].startswith("mem0-python/")


# AsyncMemoryClient is deliberately not constructed here: its validation path
# makes a real request to /v1/ping/, and a unit test that needs the network is
# worse than none. It shares _client_headers with the sync client, which is the
# code the construction test above actually guards.
def test_headers_carry_this_sdk():
    headers = _client_headers("m0-test", "u1")
    assert headers["X-Mem0-Client"].startswith("mem0-python/")


def test_our_entry_survives_a_caller_that_already_filled_the_stack():
    # Appending first and trimming to four dropped exactly the entry the
    # function exists to add.
    stack = _bounded_stack(["a/1", "b/2", "c/3", "d/4"], "mem0-python/9.9.9")

    assert "mem0-python/9.9.9" in stack
    assert len(stack.split(",")) <= 4


def test_the_character_cap_drops_whole_entries_not_characters():
    long_entries = [f"{'n' * 90}/1.0", f"{'m' * 90}/1.0", "c/3"]
    stack = _bounded_stack(long_entries, "mem0-python/9.9.9")

    assert len(stack) <= 200
    assert stack.endswith("mem0-python/9.9.9")
    for entry in stack.split(","):
        assert entry.strip().count("/") == 1, f"severed entry: {entry!r}"


def test_an_outer_stack_is_appended_to_not_replaced():
    with patch.dict(os.environ, {"MEM0_CLIENT_STACK": "openclaw/2.1.0"}):
        stack = _client_stack()

    assert stack.startswith("openclaw/2.1.0")
    assert "mem0-python/" in stack
