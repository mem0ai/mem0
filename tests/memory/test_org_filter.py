"""Tests for org-scoped multi-tenant search support (issue #4589)."""

import pytest

from mem0.memory.main import _build_filters_and_metadata


class TestBuildFiltersWithOrgId:
    """Test _build_filters_and_metadata behavior when org_id is provided."""

    def test_org_id_only(self):
        """org_id alone is a valid scope — no ValidationError raised."""
        metadata, filters = _build_filters_and_metadata(org_id="acme")
        assert filters == {"org_id": "acme"}
        # org_id should NOT be in metadata template (it's query-only)
        assert "org_id" not in metadata

    def test_org_id_with_user_id_skips_user_id_in_filters(self):
        """When org_id is present, user_id should NOT be injected into query filters."""
        metadata, filters = _build_filters_and_metadata(org_id="acme", user_id="alice")
        # user_id must NOT be in effective_query_filters — caller controls via OR
        assert "user_id" not in filters
        assert filters == {"org_id": "acme"}
        # user_id SHOULD still be in metadata template (for writes)
        assert metadata["user_id"] == "alice"

    def test_user_id_only_unchanged(self):
        """Original behavior: user_id without org_id goes into both dicts."""
        metadata, filters = _build_filters_and_metadata(user_id="alice")
        assert metadata["user_id"] == "alice"
        assert filters["user_id"] == "alice"
        assert "org_id" not in filters

    def test_org_id_with_agent_id(self):
        """org_id + agent_id: both appear in filters, agent_id also in metadata."""
        metadata, filters = _build_filters_and_metadata(org_id="acme", agent_id="bot-1")
        assert filters["org_id"] == "acme"
        assert filters["agent_id"] == "bot-1"
        assert metadata["agent_id"] == "bot-1"
        assert "org_id" not in metadata

    def test_org_id_with_user_id_and_agent_id(self):
        """org_id + user_id + agent_id: user_id skipped in filters, rest present."""
        metadata, filters = _build_filters_and_metadata(
            org_id="acme", user_id="alice", agent_id="bot-1"
        )
        assert "user_id" not in filters
        assert filters["org_id"] == "acme"
        assert filters["agent_id"] == "bot-1"
        assert metadata["user_id"] == "alice"
        assert metadata["agent_id"] == "bot-1"

    def test_no_ids_raises_validation_error(self):
        """No identifiers at all should raise Mem0ValidationError."""
        from mem0.exceptions import ValidationError as Mem0ValidationError

        with pytest.raises(Mem0ValidationError) as exc_info:
            _build_filters_and_metadata()
        assert "org_id" in str(exc_info.value)

    def test_org_id_with_input_filters_preserved(self):
        """User-supplied input_filters should be preserved alongside org_id."""
        metadata, filters = _build_filters_and_metadata(
            org_id="acme",
            input_filters={"source": "company_knowledge"},
        )
        assert filters["org_id"] == "acme"
        assert filters["source"] == "company_knowledge"

    def test_org_id_with_user_id_and_input_filters(self):
        """Full multi-tenant search scenario: org_id + user_id + OR filters."""
        metadata, filters = _build_filters_and_metadata(
            org_id="acme",
            user_id="alice",
            input_filters={
                "OR": [
                    {"user_id": "alice"},
                    {"source": "company_knowledge"},
                ],
            },
        )
        # user_id NOT injected as flat key (org_id present)
        assert "user_id" not in {k for k in filters if k != "OR"}
        assert filters["org_id"] == "acme"
        assert "OR" in filters
        assert len(filters["OR"]) == 2
