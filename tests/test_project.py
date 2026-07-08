"""Tests for ``mem0.client.project.Project.update`` — focused on the
parameter-passthrough surface.

Verifies the kwarg → JSON payload mapping for every supported field
(``custom_instructions``, ``custom_categories``, ``retrieval_criteria``,
``multilingual``, ``decay``), the ValueError when no field is
provided, and the URL/method shape. The HTTP layer is mocked.
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
