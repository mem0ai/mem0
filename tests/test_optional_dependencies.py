import builtins
import importlib
import sys
from unittest.mock import patch

import pytest

from mem0.utils.factory import VectorStoreFactory


def test_vector_store_factory_qdrant_missing_dependency_has_install_hint():
    config = {"collection_name": "test_collection", "embedding_model_dims": 1536}

    with patch(
        "mem0.utils.factory.importlib.import_module",
        side_effect=ModuleNotFoundError("No module named 'qdrant_client'"),
    ):
        with pytest.raises(ImportError, match=r"mem0ai\[qdrant\]"):
            VectorStoreFactory.create("qdrant", config)


def test_vector_store_factory_non_qdrant_provider_does_not_require_qdrant():
    class FakeChromaStore:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def fake_import(name, *args, **kwargs):
        if name == "mem0.vector_stores.qdrant":
            raise ModuleNotFoundError("No module named 'qdrant_client'")
        if name == "mem0.vector_stores.chroma":
            class _Module:
                ChromaDB = FakeChromaStore

            return _Module()
        return importlib.import_module(name, *args, **kwargs)

    config = {"collection_name": "test_collection"}
    with patch.dict(VectorStoreFactory.provider_to_class, {"chroma": "mem0.vector_stores.chroma.ChromaDB"}, clear=False):
        with patch("mem0.utils.factory.importlib.import_module", side_effect=fake_import):
            instance = VectorStoreFactory.create("chroma", config)

    assert isinstance(instance, FakeChromaStore)
    assert instance.kwargs == config


def test_telemetry_module_imports_without_posthog_and_degrades_gracefully(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "posthog":
            raise ImportError("No module named 'posthog'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("mem0.memory.telemetry", None)

    telemetry_module = importlib.import_module("mem0.memory.telemetry")
    monkeypatch.setattr(telemetry_module, "MEM0_TELEMETRY", True)

    telemetry_instance = telemetry_module.AnonymousTelemetry()

    assert telemetry_instance.posthog is None
    assert telemetry_instance.user_id is None
