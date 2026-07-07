"""Tests for auto_setup_categories.py -- the background coding-categories installer.

Covers the pure, network-free logic:
  - fingerprints (api key + category taxonomy)
  - state-file gating (load / save / is_applied)
  - idempotent apply via an injected fake client (no SDK, no network)
  - single source of truth for the category list (shared with setup_coding_categories)
"""

from __future__ import annotations

import os
import sys

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import auto_setup_categories as asc  # noqa: E402
from setup_coding_categories import CODING_CATEGORIES  # noqa: E402


# --------------------------------------------------------------------------- #
# Fake client (dependency injection — apply_categories takes a client)         #
# --------------------------------------------------------------------------- #
class _FakeProject:
    def __init__(self, current):
        self._current = current
        self.update_calls: list = []

    def get(self, fields=None):
        return {"custom_categories": self._current}

    def update(self, custom_categories=None, **kwargs):
        self.update_calls.append(custom_categories)
        return {"ok": True}


class _FakeClient:
    def __init__(self, current):
        self.project = _FakeProject(current)


# --------------------------------------------------------------------------- #
# Source-of-truth: the taxonomy is shared, not duplicated                      #
# --------------------------------------------------------------------------- #
def test_uses_shared_category_list():
    """auto_setup_categories must reuse setup_coding_categories' list, not fork it."""
    assert asc.CODING_CATEGORIES is CODING_CATEGORIES
    assert len(asc.CODING_CATEGORIES) == 17


# --------------------------------------------------------------------------- #
# Fingerprints                                                                 #
# --------------------------------------------------------------------------- #
def test_categories_fingerprint_is_stable_hex():
    fp = asc.categories_fingerprint(CODING_CATEGORIES)
    assert isinstance(fp, str)
    assert len(fp) == 16
    assert all(c in "0123456789abcdef" for c in fp)
    # deterministic across calls
    assert fp == asc.categories_fingerprint(CODING_CATEGORIES)


def test_categories_fingerprint_changes_when_taxonomy_changes():
    base = asc.categories_fingerprint(CODING_CATEGORIES)
    changed = asc.categories_fingerprint(CODING_CATEGORIES + [{"new_one": "desc"}])
    assert base != changed


def test_categories_fingerprint_order_independent():
    """Reordering the same categories must yield the same fingerprint."""
    reordered = list(reversed(CODING_CATEGORIES))
    assert asc.categories_fingerprint(CODING_CATEGORIES) == asc.categories_fingerprint(reordered)


def test_apikey_fingerprint_is_stable_and_opaque():
    key = "m0-supersecret-abc123"
    fp = asc.apikey_fingerprint(key)
    assert isinstance(fp, str)
    assert len(fp) == 16
    assert fp == asc.apikey_fingerprint(key)
    # never leak the raw key
    assert "supersecret" not in fp
    assert key not in fp


def test_apikey_fingerprint_differs_per_key():
    assert asc.apikey_fingerprint("m0-aaa") != asc.apikey_fingerprint("m0-bbb")


# --------------------------------------------------------------------------- #
# State file: load / save / gating                                            #
# --------------------------------------------------------------------------- #
def test_load_state_missing_file_returns_empty(tmp_path):
    assert asc.load_state(str(tmp_path / "does_not_exist.json")) == {}


def test_load_state_corrupt_file_returns_empty(tmp_path):
    p = tmp_path / "categories_setup.json"
    p.write_text("{not valid json")
    assert asc.load_state(str(p)) == {}


def test_save_then_load_roundtrip_creates_parent_dir(tmp_path):
    p = tmp_path / "nested" / "categories_setup.json"
    asc.save_state({"abc123": "deadbeef00000000"}, str(p))
    assert p.is_file()
    assert asc.load_state(str(p)) == {"abc123": "deadbeef00000000"}


def test_is_applied_true_only_on_exact_match():
    state = {"keyfp": "catfp"}
    assert asc.is_applied(state, "keyfp", "catfp") is True
    # stale taxonomy fingerprint
    assert asc.is_applied(state, "keyfp", "OTHER") is False
    # unknown api key
    assert asc.is_applied(state, "other-key", "catfp") is False
    # empty state
    assert asc.is_applied({}, "keyfp", "catfp") is False


# --------------------------------------------------------------------------- #
# apply_categories: idempotent, network-free via fake client                  #
# --------------------------------------------------------------------------- #
def test_apply_skips_update_when_already_matching():
    client = _FakeClient(CODING_CATEGORIES)
    result = asc.apply_categories(client, CODING_CATEGORIES)
    assert result == "already-configured"
    assert client.project.update_calls == []  # must NOT hit the write endpoint


def test_apply_updates_when_no_categories_set():
    client = _FakeClient(None)
    result = asc.apply_categories(client, CODING_CATEGORIES)
    assert result == "applied"
    assert client.project.update_calls == [CODING_CATEGORIES]


def test_apply_updates_when_categories_differ():
    client = _FakeClient([{"food": "consumer default"}])
    result = asc.apply_categories(client, CODING_CATEGORIES)
    assert result == "applied"
    assert client.project.update_calls == [CODING_CATEGORIES]


def test_fetch_current_categories_handles_non_dict():
    """A non-dict project response must degrade to None, not raise."""

    class Weird:
        project = type("P", (), {"get": staticmethod(lambda fields=None: "unexpected")})()

    assert asc.fetch_current_categories(Weird()) is None
