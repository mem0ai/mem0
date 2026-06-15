"""Tests for hostname identity resolution (task_04 / ADR-003).

The MCP ``user_id`` slot carries the machine hostname for *attribution only*.
These tests cover :func:`app.utils.identity.resolve_hostname`:

- a present hostname is used as-is (trimmed);
- a missing/blank hostname falls back to the explicit sentinel without raising
  (the PRD's open question on absent hostname);

The companion assertion that identity is NOT used as a read filter lives in
``test_mcp_read_project.py`` (search/list never put ``user_id`` in the filters);
``test_mcp_write_enqueue.py`` asserts the resolved hostname reaches the write job.
"""

from app.utils.identity import DEFAULT_HOSTNAME, resolve_hostname


class TestResolveHostname:
    def test_present_hostname_used_as_is(self):
        assert resolve_hostname("maqA") == "maqA"

    def test_hostname_is_trimmed(self):
        assert resolve_hostname("  maqA  ") == "maqA"

    def test_none_falls_back_to_default(self):
        assert resolve_hostname(None) == DEFAULT_HOSTNAME

    def test_empty_falls_back_to_default(self):
        assert resolve_hostname("") == DEFAULT_HOSTNAME

    def test_whitespace_falls_back_to_default(self):
        assert resolve_hostname("   ") == DEFAULT_HOSTNAME

    def test_default_is_a_stable_sentinel(self):
        # Audit/catalog rely on a single well-known value.
        assert DEFAULT_HOSTNAME == "unknown-host"
