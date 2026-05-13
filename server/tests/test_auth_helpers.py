"""Unit tests for _ensure_admin and require_admin in server/auth.py."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def _fake_request(auth_type: str = "none"):
    return SimpleNamespace(state=SimpleNamespace(auth_type=auth_type))


def test_ensure_admin_passes_for_admin_user(admin_user):
    from auth import _ensure_admin

    _ensure_admin(_fake_request("bearer"), admin_user)  # must not raise


def test_ensure_admin_passes_for_admin_api_key_auth_type():
    from auth import _ensure_admin

    _ensure_admin(_fake_request("admin_api_key"), None)  # must not raise


def test_ensure_admin_passes_for_auth_disabled():
    from auth import _ensure_admin

    _ensure_admin(_fake_request("disabled"), None)  # must not raise


def test_ensure_admin_rejects_non_admin_user(member_user):
    from auth import _ensure_admin

    with pytest.raises(HTTPException) as exc:
        _ensure_admin(_fake_request("bearer"), member_user)
    assert exc.value.status_code == 403
    assert "Admin role required" in exc.value.detail


def test_ensure_admin_rejects_no_user_with_no_legacy_path():
    from auth import _ensure_admin

    with pytest.raises(HTTPException) as exc:
        _ensure_admin(_fake_request("none"), None)
    assert exc.value.status_code == 403


def test_ensure_admin_rejects_bearer_with_no_user():
    """Defense-in-depth: a 'bearer' auth_type without a User should not pass."""
    from auth import _ensure_admin

    with pytest.raises(HTTPException) as exc:
        _ensure_admin(_fake_request("bearer"), None)
    assert exc.value.status_code == 403
