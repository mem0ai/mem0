"""The fixture set is the yardstick for the write gate, so the yardstick itself is tested.

A malformed fixture silently changes what the harness measures -- a typo'd label would
quietly move a window out of the drop class and inflate hard-drop recall forever. These
tests are cheap and they run without the network.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from mem0_agent.config.project_config import TYPES

REQUIRED_KEYS = {"id", "window", "label", "expect_type", "note"}
VALID_LABELS = {"drop", "exclude", "extract"}
MIN_FIXTURES = 40


def _load_fixtures():
    """eval/ is a script directory, not a package -- load the module by path."""
    path = Path(__file__).resolve().parents[1] / "eval" / "fixtures.py"
    spec = importlib.util.spec_from_file_location("eval_fixtures", path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fx = _load_fixtures()


def test_fixture_count():
    assert len(fx.FIXTURES) >= MIN_FIXTURES, f"need at least {MIN_FIXTURES} fixtures for a meaningful score"


def test_all_labels_represented():
    counts = fx.counts()
    assert set(counts) == VALID_LABELS
    for label, n in counts.items():
        assert n >= 5, f"label {label!r} has only {n} fixtures; too few to score"


def test_ids_unique():
    ids = [f["id"] for f in fx.FIXTURES]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate fixture ids: {sorted(dupes)}"


@pytest.mark.parametrize("fixture", fx.FIXTURES, ids=lambda f: f["id"])
def test_fixture_schema(fixture):
    assert REQUIRED_KEYS <= set(fixture), f"missing keys: {sorted(REQUIRED_KEYS - set(fixture))}"
    assert isinstance(fixture["id"], str) and fixture["id"]
    assert fixture["label"] in VALID_LABELS
    assert isinstance(fixture["note"], str) and fixture["note"].strip(), "every fixture must say why it exists"


@pytest.mark.parametrize("fixture", fx.FIXTURES, ids=lambda f: f["id"])
def test_window_shape(fixture):
    window = fixture["window"]
    assert isinstance(window, list) and window, "window must be a non-empty list of messages"
    for msg in window:
        assert set(msg) == {"role", "content"}, f"message keys must be role/content, got {sorted(msg)}"
        assert msg["role"] in {"user", "assistant"}
        assert isinstance(msg["content"], str) and msg["content"].strip()


@pytest.mark.parametrize("fixture", fx.FIXTURES, ids=lambda f: f["id"])
def test_expect_type(fixture):
    want = fixture["expect_type"]
    if fixture["label"] == "extract":
        assert want in TYPES, f"extract fixtures need an expect_type from TYPES, got {want!r}"
    else:
        assert want is None, f"{fixture['label']} fixtures must not claim a type, got {want!r}"


def test_extract_covers_every_durable_type():
    from mem0_agent.config.project_config import DURABLE_TYPES

    covered = set(fx.counts_by_type())
    assert set(DURABLE_TYPES) <= covered, f"no extract fixture for {sorted(set(DURABLE_TYPES) - covered)}"


def test_helpers_agree():
    assert sum(fx.counts().values()) == len(fx.FIXTURES)
    assert sum(fx.counts_by_type().values()) == len(fx.by_label("extract"))
    assert fx.get("e01_pref_test_output_first") is not None
    assert fx.get("nope_not_a_fixture") is None
