"""Conformance tests for the canonical JSON strict profile v1 (RFC #7376).

Self-contained: no dependency on any bundle implementation. The vectors
in ``conformance/canonical_vectors.json`` are the source of truth; any
implementation claiming strict-profile compliance must pass them
byte-for-byte, and the same vectors are verified against an independent
JavaScript implementation via ``conformance/verify_cross_engine.mjs``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mem0.memory.canonical_json import CanonicalJSONError, canonical_dumps

VECTORS_PATH = Path(__file__).parent / "conformance" / "canonical_vectors.json"


def _vectors():
    return json.loads(VECTORS_PATH.read_text(encoding="utf-8"))["vectors"]


@pytest.mark.parametrize("vector", _vectors(), ids=lambda v: v["name"])
def test_conformance_vector(vector):
    """Every vector: parse input JSON text -> canonical_dumps == expected bytes."""
    value = json.loads(vector["input"])
    assert canonical_dumps(value) == vector["expected"]


@pytest.mark.parametrize("vector", _vectors(), ids=lambda v: v["name"])
def test_canonicalization_is_idempotent(vector):
    """Canonical output re-parsed and re-canonicalized is a fixed point."""
    once = canonical_dumps(json.loads(vector["input"]))
    assert canonical_dumps(json.loads(once)) == once


def test_reject_nan_fail_closed():
    with pytest.raises(CanonicalJSONError):
        canonical_dumps(float("nan"))


def test_reject_infinity_fail_closed():
    with pytest.raises(CanonicalJSONError):
        canonical_dumps([float("inf"), float("-inf")])


def test_reject_lone_surrogate_fail_closed():
    with pytest.raises(CanonicalJSONError):
        canonical_dumps("\ud800")


def test_reject_non_string_key():
    with pytest.raises(CanonicalJSONError):
        canonical_dumps({1: "a"})


def test_reject_non_json_type():
    with pytest.raises(CanonicalJSONError):
        canonical_dumps(object())


def test_motivating_divergence_is_real():
    """The failure this profile exists for: naive json.dumps is not stable.

    Python emits '1e+16'; a JavaScript exporter emits '10000000000000000';
    an importer digesting those bytes sees different content for the same
    logical value. The strict profile pins one byte form.
    """
    assert json.dumps(1e16) == "1e+16"  # naive: runtime-specific
    assert canonical_dumps(1e16) == "1e16"  # strict profile: pinned
    assert json.dumps(1e-7) == "1e-07"  # naive: zero-padded exponent
    assert canonical_dumps(1e-7) == "1e-7"  # strict profile: pinned


def test_digest_stability_across_roundtrip():
    """sha256 over canonical bytes must be invariant to key insertion order."""
    import hashlib

    a = {"score": 0.5, "id": "m1", "meta": {"source": "x", "ts": 1}}
    b = {"meta": {"ts": 1, "source": "x"}, "id": "m1", "score": 0.5}
    da = hashlib.sha256(canonical_dumps(a).encode("utf-8")).hexdigest()
    db = hashlib.sha256(canonical_dumps(b).encode("utf-8")).hexdigest()
    assert da == db
