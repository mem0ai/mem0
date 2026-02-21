import pytest

from mem0.exceptions import ValidationError as Mem0ValidationError
from mem0.memory.main import Memory


@pytest.fixture
def memory(mocker):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mocker.patch("mem0.utils.factory.VectorStoreFactory.create", mock_vector_store)

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)

    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    instance = Memory()
    instance.config = mocker.MagicMock()
    instance.config.custom_fact_extraction_prompt = None
    instance.config.custom_update_memory_prompt = None
    instance.config.llm = mocker.MagicMock()
    instance.config.llm.config = {}
    instance.api_version = "v1.1"

    return instance


def test_add_requires_session_id(memory):
    with pytest.raises(Mem0ValidationError) as excinfo:
        memory.add("hello")

    assert excinfo.value.error_code == "VALIDATION_001"


def test_add_rejects_invalid_memory_type(memory):
    with pytest.raises(Mem0ValidationError) as excinfo:
        memory.add("hello", user_id="user-1", memory_type="invalid")

    assert excinfo.value.error_code == "VALIDATION_002"


def test_add_rejects_invalid_messages_type(memory):
    with pytest.raises(Mem0ValidationError) as excinfo:
        memory.add(123, user_id="user-1")

    assert excinfo.value.error_code == "VALIDATION_003"
