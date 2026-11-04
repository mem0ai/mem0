"""Tests for keeping the vector store embedding dimension in sync with the embedder."""

import json
from unittest.mock import MagicMock

import pytest

from mem0.configs.base import MemoryConfig
from mem0.configs.vector_stores.pgvector import PGVectorConfig
from mem0.utils.embedding_dims import resolve_embedding_dims
from mem0.vector_stores.configs import VectorStoreConfig


def _embedder(dims):
    embedder = MagicMock()
    embedder.config.embedding_dims = dims
    return embedder


def _pgvector_config_dict(**kwargs):
    """Return the vector store configuration as the dict the config models expect.

    ``embedding_model_dims`` is only included when the caller asks for it, so the
    default stays "not configured by the user".
    """
    defaults = {
        "user": "user",
        "password": "password",
        "host": "localhost",
        "port": 5432,
        "collection_name": "mem0",
    }
    defaults.update(kwargs)
    return defaults


def _pgvector_config(**kwargs):
    return PGVectorConfig(**_pgvector_config_dict(**kwargs))


class TestResolveEmbeddingDims:
    def test_infers_dimension_from_embedder_when_not_configured(self):
        config = _pgvector_config()

        resolved = resolve_embedding_dims(_embedder(768), config, "pgvector")

        assert resolved == 768
        assert config.embedding_model_dims == 768

    def test_keeps_explicit_matching_dimension(self):
        config = _pgvector_config(embedding_model_dims=768)

        resolved = resolve_embedding_dims(_embedder(768), config, "pgvector")

        assert resolved == 768
        assert config.embedding_model_dims == 768

    def test_raises_on_explicit_mismatch(self):
        config = _pgvector_config(embedding_model_dims=1536)

        with pytest.raises(ValueError, match="Embedding dimension mismatch"):
            resolve_embedding_dims(_embedder(768), config, "pgvector")

        assert config.embedding_model_dims == 1536

    def test_ignores_embedder_with_unknown_dimension(self):
        config = _pgvector_config()

        assert resolve_embedding_dims(_embedder(None), config, "pgvector") is None
        assert config.embedding_model_dims == 1536

    def test_ignores_store_without_dimension_field(self):
        class StoreWithoutDims:
            pass

        store_config = StoreWithoutDims()

        assert resolve_embedding_dims(_embedder(768), store_config, "chroma") is None
        assert not hasattr(store_config, "embedding_model_dims")

    def test_inferred_dimension_is_not_treated_as_explicit(self):
        """A dimension Mem0 inferred itself must not be mistaken for a user choice."""
        config = _pgvector_config()

        resolve_embedding_dims(_embedder(768), config, "pgvector")

        assert "embedding_model_dims" not in config.model_fields_set
        assert config.embedding_model_dims == 768

    def test_inferred_dimension_can_be_re_inferred_for_another_embedder(self):
        """Re-using a config with a different embedder re-infers instead of failing."""
        config = _pgvector_config()

        assert resolve_embedding_dims(_embedder(768), config, "pgvector") == 768
        assert resolve_embedding_dims(_embedder(1024), config, "pgvector") == 1024
        assert config.embedding_model_dims == 1024

    def test_explicit_dimension_still_mismatches_after_resolution(self):
        """A dimension the user configured keeps failing when it disagrees."""
        config = _pgvector_config(embedding_model_dims=768)

        with pytest.raises(ValueError, match="Embedding dimension mismatch"):
            resolve_embedding_dims(_embedder(1024), config, "pgvector")

    def test_supports_alternative_dimension_field_name(self):
        """Some stores name the field differently (Databricks: ``embedding_dimension``)."""
        from pydantic import BaseModel, Field

        class StoreConfig(BaseModel):
            embedding_dimension: int = Field(1536)

        config = StoreConfig()

        assert resolve_embedding_dims(_embedder(768), config, "databricks") == 768
        assert config.embedding_dimension == 768

    def test_supports_dict_configuration(self):
        config = {"embedding_model_dims": 1536}

        with pytest.raises(ValueError, match="Embedding dimension mismatch"):
            resolve_embedding_dims(_embedder(768), config, "pgvector")

    def test_infers_dimension_for_dict_configuration(self):
        config = {}

        assert resolve_embedding_dims(_embedder(768), config, "pgvector") == 768
        assert config["embedding_model_dims"] == 768


def _patch_factories(mocker, dims=768):
    embedder = _embedder(dims)
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=embedder)
    mocker.patch("mem0.utils.factory.VectorStoreFactory.create", return_value=MagicMock())
    mocker.patch("mem0.utils.factory.LlmFactory.create", return_value=MagicMock())
    mocker.patch("mem0.memory.main.SQLiteManager", MagicMock())
    mocker.patch("mem0.memory.main.capture_event", MagicMock())
    return embedder


class TestMemoryAppliesEmbeddingDims:
    def test_memory_infers_dimension_from_embedder(self, mocker):
        from mem0.memory.main import Memory

        _patch_factories(mocker, dims=768)

        config = MemoryConfig(
            vector_store=VectorStoreConfig(
                provider="pgvector",
                config=_pgvector_config_dict(),
            )
        )
        memory = Memory(config)

        assert memory.config.vector_store.config.embedding_model_dims == 768

    def test_memory_raises_on_explicit_mismatch(self, mocker):
        from mem0.memory.main import Memory

        _patch_factories(mocker, dims=768)

        config = MemoryConfig(
            vector_store=VectorStoreConfig(
                provider="pgvector",
                config=_pgvector_config_dict(embedding_model_dims=1536),
            )
        )

        with pytest.raises(ValueError, match="Embedding dimension mismatch"):
            Memory(config)

    @pytest.mark.asyncio
    async def test_async_memory_infers_dimension_from_embedder(self, mocker):
        from mem0.memory.main import AsyncMemory

        _patch_factories(mocker, dims=768)

        config = MemoryConfig(
            vector_store=VectorStoreConfig(
                provider="pgvector",
                config=_pgvector_config_dict(),
            )
        )
        memory = AsyncMemory(config)

        assert memory.config.vector_store.config.embedding_model_dims == 768

    def test_default_config_is_not_shared_between_instances(self, mocker):
        """Two memories without a config must not share (and mutate) one config object."""
        from mem0.memory.main import Memory

        _patch_factories(mocker, dims=768)

        first = Memory()
        second = Memory()

        assert first.config is not second.config
        assert first.config.vector_store.config is not second.config.vector_store.config

    def test_shared_config_with_different_embedders_does_not_raise(self, mocker):
        """Re-using one config for two embedders re-infers the dimension instead of failing."""
        from mem0.memory.main import Memory

        embedders = [_embedder(768), _embedder(1024)]
        mocker.patch(
            "mem0.utils.factory.EmbedderFactory.create", side_effect=embedders
        )
        created_dims = []

        def create_vector_store(provider, config, **kwargs):
            created_dims.append(config.embedding_model_dims)
            return MagicMock()

        mocker.patch(
            "mem0.utils.factory.VectorStoreFactory.create",
            side_effect=create_vector_store,
        )
        mocker.patch("mem0.utils.factory.LlmFactory.create", return_value=MagicMock())
        mocker.patch("mem0.memory.main.SQLiteManager", MagicMock())
        mocker.patch("mem0.memory.main.capture_event", MagicMock())

        config = MemoryConfig(
            vector_store=VectorStoreConfig(
                provider="pgvector",
                config=_pgvector_config_dict(),
            )
        )

        Memory(config)
        Memory(config)

        # Each store is created with the dimension of the embedder it was built for.
        midpoint = len(created_dims) // 2
        assert created_dims[:midpoint] == [768] * midpoint
        assert created_dims[midpoint:] == [1024] * midpoint


class TestDimensionMismatchIsNotSwallowed:
    """A rejected write must surface the reason instead of a generic failure."""

    def _memory(self, mocker, insert_error):
        from mem0.memory.main import Memory

        embedder = _embedder(768)
        embedder.embed.return_value = [0.1] * 768
        embedder.embed_batch.return_value = [[0.1] * 768]
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=embedder)

        vector_store = MagicMock()
        vector_store.search.return_value = []
        vector_store.insert.side_effect = insert_error
        mocker.patch("mem0.utils.factory.VectorStoreFactory.create", return_value=vector_store)

        llm = MagicMock()
        llm.generate_response.return_value = json.dumps(
            {"memory": [{"id": "0", "text": "test memory", "event": "ADD"}]}
        )
        mocker.patch("mem0.utils.factory.LlmFactory.create", return_value=llm)
        mocker.patch("mem0.memory.main.SQLiteManager", MagicMock())
        mocker.patch("mem0.memory.main.capture_event", MagicMock())

        memory = Memory()
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        return memory

    def test_insert_failure_reports_the_underlying_cause(self, mocker):
        from mem0.exceptions import VectorStoreError

        memory = self._memory(
            mocker,
            ValueError(
                "Embedding dimension mismatch: the embedder produced a 768-dimension vector, "
                "but the 'mem0' collection is configured with embedding_model_dims=1536."
            ),
        )

        with pytest.raises(VectorStoreError) as exc:
            memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
                filters={"user_id": "u1"},
                infer=True,
            )

        assert "Embedding dimension mismatch" in str(exc.value)
