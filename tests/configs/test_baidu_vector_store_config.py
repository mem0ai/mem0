from unittest.mock import Mock, patch

from mem0.configs.base import MemoryConfig

BAIDU_VECTOR_STORE = {
    "provider": "baidu",
    "config": {
        "endpoint": "http://localhost:8287",
        "account": "root",
        "api_key": "key",
        "database_name": "mem0",
        "table_name": "mem0_table",
        "embedding_model_dims": 1536,
        "metric_type": "COSINE",
    },
}


def test_baidu_config_exposes_the_collection_name_memory_reads():
    config = MemoryConfig(vector_store=BAIDU_VECTOR_STORE)

    assert config.vector_store.config.collection_name == "mem0"


def test_memory_can_be_built_from_the_documented_baidu_config(tmp_path):
    from mem0.memory.main import Memory

    with (
        patch("mem0.memory.main.EmbedderFactory") as embedder,
        patch("mem0.memory.main.VectorStoreFactory") as vector_store,
        patch("mem0.memory.main.LlmFactory") as llm,
        patch("mem0.memory.telemetry.capture_event"),
    ):
        embedder.create.return_value = Mock()
        vector_store.create.return_value = Mock()
        llm.create.return_value = Mock()

        memory = Memory(
            MemoryConfig(
                vector_store=BAIDU_VECTOR_STORE,
                history_db_path=str(tmp_path / "history.db"),
            )
        )

    assert memory.collection_name == "mem0"
