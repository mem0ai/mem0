"""Regressions for the self-hosted /search payload shape.

The self-hosted server returns the SDK payload wrapped one extra level
(``{"results": {"results": [...]}}``) while the platform and OSS backends return it
single-level. Before the fix, ``_unwrap_results`` returned the inner dict, so callers
raised ``AttributeError: 'str' object has no attribute 'get'`` when iterating the dict's
keys, or saw an empty result list and reported "no memories found".
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def backend():
    spec = importlib.util.spec_from_file_location("hermes_plugin_mem0_backend", ROOT / "_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_level_dict_is_unchanged(backend):
    payload = {"results": [{"id": "1", "memory": "a"}, {"id": "2", "memory": "b"}]}
    assert backend._unwrap_results(payload) == payload["results"]


def test_doubly_nested_dict_is_unwrapped(backend):
    # the shape a stock self-hosted /search returns
    payload = {"results": {"results": [{"id": "1", "memory": "a"}]}}
    assert backend._unwrap_results(payload) == [{"id": "1", "memory": "a"}]


def test_triple_nesting_is_unwrapped(backend):
    payload = {"results": {"results": {"results": [{"memory": "x"}]}}}
    assert backend._unwrap_results(payload) == [{"memory": "x"}]


def test_plain_list_passes_through(backend):
    payload = [{"memory": "a"}]
    assert backend._unwrap_results(payload) == payload


def test_bare_strings_are_normalized_to_dicts(backend):
    assert backend._unwrap_results(["a", "b"]) == [{"memory": "a"}, {"memory": "b"}]


def test_empty_and_unexpected_shapes_never_raise(backend):
    assert backend._unwrap_results({}) == []
    assert backend._unwrap_results({"'results'": []}) == []
    assert backend._unwrap_results(None) == []
    assert backend._unwrap_results("nope") == []


def test_items_missing_the_memory_key_are_preserved(backend):
    # get()/get_all() reuse this helper; only real items must survive, unshaped is fine
    payload = {"results": {"results": [{"id": "1"}]}}
    assert backend._unwrap_results(payload) == [{"id": "1"}]
