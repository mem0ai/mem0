"""Regression test for Turbopuffer filter operator conversion."""

import importlib
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import MagicMock


def test_issue_6562(monkeypatch):
    """Turbopuffer must not silently drop a ``gt`` filter."""

    repository_root = Path(__file__).parents[1]
    mem0 = ModuleType("mem0")
    mem0.__path__ = [str(repository_root / "mem0")]
    vector_stores = ModuleType("mem0.vector_stores")
    vector_stores.__path__ = [str(repository_root / "mem0" / "vector_stores")]
    turbopuffer = ModuleType("turbopuffer")
    turbopuffer.Turbopuffer = MagicMock()

    monkeypatch.setitem(sys.modules, "mem0", mem0)
    monkeypatch.setitem(sys.modules, "mem0.vector_stores", vector_stores)
    monkeypatch.setitem(sys.modules, "turbopuffer", turbopuffer)
    monkeypatch.delitem(sys.modules, "mem0.vector_stores.turbopuffer", raising=False)

    module = importlib.import_module("mem0.vector_stores.turbopuffer")
    db = object.__new__(module.TurbopufferDB)

    assert db._convert_filters({"age": {"gt": 18}}) == ("age", "Gt", 18)
