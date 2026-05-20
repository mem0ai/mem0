"""Regression test for issue #3800.

Hatch 1.16.x normalizes extra/feature names per PEP 503/508 (underscores ->
hyphens).  This test ensures that ``vector_stores`` has been renamed to
``vector-stores`` in pyproject.toml so that the normalized lookup succeeds and
``hatch shell`` no longer raises a ValueError.
"""

import re
from pathlib import Path

import pytest


PYPROJECT = Path(__file__).parents[1] / "pyproject.toml"


def _read_pyproject():
    return PYPROJECT.read_text(encoding="utf-8")


def test_optional_dependency_uses_hyphen():
    """[project.optional-dependencies] must define 'vector-stores', not 'vector_stores'."""
    content = _read_pyproject()
    # The section header must use a hyphen
    assert re.search(r'^\s*vector-stores\s*=\s*\[', content, re.MULTILINE), (
        "Expected 'vector-stores' (hyphenated) in [project.optional-dependencies]; "
        "found underscore form which breaks Hatch 1.16+ environment setup."
    )
    # The underscore form must not be present as a key
    assert not re.search(r'^\s*vector_stores\s*=\s*\[', content, re.MULTILINE), (
        "'vector_stores' (underscore) must not appear as an optional-dependency key; "
        "use 'vector-stores' instead."
    )


def test_hatch_env_features_use_hyphen():
    """All [tool.hatch.envs.*] features lists must reference 'vector-stores', not 'vector_stores'."""
    content = _read_pyproject()
    assert '"vector-stores"' in content, (
        "Expected '\"vector-stores\"' in hatch env features; "
        "found underscore form which breaks Hatch 1.16+ environment setup."
    )
    assert '"vector_stores"' not in content, (
        "'\"vector_stores\"' (underscore) must not appear in hatch env features; "
        "use '\"vector-stores\"' instead."
    )
