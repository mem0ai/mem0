"""Tests for ``mem0.client.project.Project.update`` — focused on the
parameter-passthrough surface.

Verifies the kwarg → JSON payload mapping for every supported field
(``custom_instructions``, ``custom_categories``, ``multilingual``,
``decay``, ``agent_custom_instructions``), the ValueError when no field
is provided, and the URL/method shape. The HTTP layer is mocked.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def project():
    """Build a ``Project`` with a mocked httpx client.

    Bypasses ``MemoryClient`` so the test stays focused on
    ``Project.update`` payload construction.
    """
    http = MagicMock()
    http.patch.return_value = MagicMock(
        json=lambda: {"message": "Updated"},
        raise_for_status=lambda: None,
    )
    with patch("mem0.client.project.capture_client_event"):
        from mem0.client.project import Project

        proj = Project(client=http, org_id="org1", project_id="proj1")
        yield proj, http


def _patch_payload(http):
    """Return the JSON body sent on the last PATCH, stripped of the SDK's
    standard auth params (``org_id``, ``project_id``) that ``_prepare_params``
    injects on every request."""
    assert http.patch.called, "expected a PATCH call"
    _, kwargs = http.patch.call_args
    body = dict(kwargs.get("json", {}))
    body.pop("org_id", None)
    body.pop("project_id", None)
    return body


class TestProjectUpdateDecay:
    def test_decay_true_sent_in_payload(self, project):
        proj, http = project
        proj.update(decay=True)
        assert _patch_payload(http) == {"decay": True}

    def test_decay_false_sent_in_payload(self, project):
        """Explicit ``False`` must round-trip — not be filtered as falsy."""
        proj, http = project
        proj.update(decay=False)
        assert _patch_payload(http) == {"decay": False}

    def test_decay_combined_with_multilingual(self, project):
        proj, http = project
        proj.update(multilingual=True, decay=True)
        assert _patch_payload(http) == {
            "multilingual": True,
            "decay": True,
        }

    def test_decay_omitted_when_none(self, project):
        """When the caller doesn't pass ``decay``, it must not appear in
        the payload — backwards compatible with pre-decay callers."""
        proj, http = project
        proj.update(multilingual=False)
        payload = _patch_payload(http)
        assert payload == {"multilingual": False}
        assert "decay" not in payload

    def test_no_args_raises_with_decay_in_message(self, project):
        proj, _ = project
        with pytest.raises(ValueError, match=r"decay"):
            proj.update()

    def test_url_targets_project_endpoint(self, project):
        proj, http = project
        proj.update(decay=True)
        args, _ = http.patch.call_args
        assert args[0] == "/api/v1/orgs/organizations/org1/projects/proj1/"


class TestProjectUpdateAgentCustomInstructions:
    def test_agent_custom_instructions_sent_in_payload(self, project):
        proj, http = project
        proj.update(agent_custom_instructions="remember tool failures")
        assert _patch_payload(http) == {"agent_custom_instructions": "remember tool failures"}

    def test_agent_custom_instructions_alone_satisfies_the_guard(self, project):
        """It is a standalone field, so setting only it must not raise."""
        proj, http = project
        proj.update(agent_custom_instructions="remember tool failures")
        assert http.patch.called

    def test_empty_string_round_trips_to_clear_the_field(self, project):
        """An empty string must survive the ``is not None`` filter, not be dropped as falsy."""
        proj, http = project
        proj.update(agent_custom_instructions="")
        assert _patch_payload(http) == {"agent_custom_instructions": ""}

    def test_combined_with_custom_instructions(self, project):
        """Both sets in one PATCH: the split-instruction configuration."""
        proj, http = project
        proj.update(
            custom_instructions="remember user preferences",
            agent_custom_instructions="remember tool failures",
        )
        assert _patch_payload(http) == {
            "custom_instructions": "remember user preferences",
            "agent_custom_instructions": "remember tool failures",
        }

    def test_omitted_when_none(self, project):
        """Callers that don't pass it must send an unchanged payload."""
        proj, http = project
        proj.update(custom_instructions="be concise")
        payload = _patch_payload(http)
        assert payload == {"custom_instructions": "be concise"}
        assert "agent_custom_instructions" not in payload

    def test_no_args_raises_with_agent_instructions_in_message(self, project):
        proj, _ = project
        with pytest.raises(ValueError, match=r"agent_custom_instructions"):
            proj.update()


class TestProjectUpdateBackwardsCompat:
    def test_multilingual_only_still_works(self, project):
        """Pre-decay callers (multilingual only) keep working unchanged."""
        proj, http = project
        proj.update(multilingual=True)
        assert _patch_payload(http) == {"multilingual": True}

    def test_custom_instructions_only_still_works(self, project):
        proj, http = project
        proj.update(custom_instructions="be concise")
        assert _patch_payload(http) == {"custom_instructions": "be concise"}
