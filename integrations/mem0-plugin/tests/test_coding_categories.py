"""Tests for setup_coding_categories.py -- CODING_CATEGORIES list completeness."""

from __future__ import annotations

import importlib
import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")

EXPECTED_KEYS = [
    "architecture_decisions",
    "anti_patterns",
    "task_learnings",
    "tooling_setup",
    "bug_fixes",
    "coding_conventions",
    "user_preferences",
    "dependency_decisions",
    "performance_findings",
    "security_constraints",
    "testing_patterns",
    "data_model",
    "api_contracts",
    "deployment_runbook",
    "team_norms",
    "domain_glossary",
    "experiment_results",
]


@pytest.fixture()
def coding_categories():
    """Import CODING_CATEGORIES from setup_coding_categories, ensuring scripts/ is on path."""
    abs_scripts = os.path.abspath(SCRIPTS_DIR)
    inserted = False
    if abs_scripts not in sys.path:
        sys.path.insert(0, abs_scripts)
        inserted = True
    # Force re-import in case another test already loaded a stale version
    mod_name = "setup_coding_categories"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    mod = importlib.import_module(mod_name)
    yield mod.CODING_CATEGORIES
    if inserted and abs_scripts in sys.path:
        sys.path.remove(abs_scripts)


def test_total_count(coding_categories):
    """CODING_CATEGORIES must contain exactly 17 entries."""
    assert len(coding_categories) == 17, (
        f"Expected 17 categories, found {len(coding_categories)}: "
        f"{[list(c.keys())[0] for c in coding_categories]}"
    )


def test_all_expected_keys_present(coding_categories):
    """Every expected category key must appear exactly once."""
    actual_keys = [list(cat.keys())[0] for cat in coding_categories]
    for key in EXPECTED_KEYS:
        assert key in actual_keys, f"Missing expected category key: '{key}'"


def test_no_duplicate_keys(coding_categories):
    """No category key may appear more than once."""
    actual_keys = [list(cat.keys())[0] for cat in coding_categories]
    seen = set()
    duplicates = []
    for key in actual_keys:
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    assert not duplicates, f"Duplicate category keys found: {duplicates}"


def test_each_description_is_non_empty_string(coding_categories):
    """Every category must have a non-empty string description."""
    for cat in coding_categories:
        assert len(cat) == 1, f"Category dict should have exactly one key, got: {cat}"
        key = list(cat.keys())[0]
        description = cat[key]
        assert isinstance(description, str), (
            f"Category '{key}' description is not a string: {type(description)}"
        )
        assert description.strip(), f"Category '{key}' has an empty description"
