import pytest
from unittest.mock import Mock
from mem0.memory.main import Memory


@pytest.fixture
def memory_store():
    return Memory()


@pytest.fixture
def memory_instance():
    return Memory()


@pytest.mark.skip(reason="Not implemented")
def test_create_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    assert memory_store.get(memory_id) == data


@pytest.mark.skip(reason="Not implemented")
def test_get_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    retrieved_data = memory_store.get(memory_id)
    assert retrieved_data == data


@pytest.mark.skip(reason="Not implemented")
def test_update_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    new_data = "Name is John Kapoor."
    updated_memory = memory_store.update(memory_id, new_data)
    assert updated_memory == new_data
    assert memory_store.get(memory_id) == new_data


@pytest.mark.skip(reason="Not implemented")
def test_delete_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    memory_store.delete(memory_id)
    assert memory_store.get(memory_id) is None


@pytest.mark.skip(reason="Not implemented")
def test_history(memory_store):
    data = "I like Indian food."
    memory_id = memory_store.create(data=data)
    history = memory_store.history(memory_id)
    assert history == [data]
    assert memory_store.get(memory_id) == data

    new_data = "I like Italian food."
    memory_store.update(memory_id, new_data)
    history = memory_store.history(memory_id)
    assert history == [data, new_data]
    assert memory_store.get(memory_id) == new_data


@pytest.mark.skip(reason="Not implemented")
def test_list_memories(memory_store):
    data1 = "Name is John Doe."
    data2 = "Name is John Doe. I like to code in Python."
    memory_store.create(data=data1)
    memory_store.create(data=data2)
    memories = memory_store.list()
    assert data1 in memories
    assert data2 in memories


def test_add_memory_success(memory_instance):
    memory_instance.llm.generate_response = Mock(return_value='{"memory": [{"event": "ADD", "text": "New memory added."}]}')
    memory_instance.remove_code_blocks = Mock(return_value='{"memory": [{"event": "ADD", "text": "New memory added."}]}')

    result = memory_instance.add(messages="Test message", user_id="user1")

    assert len(result) == 1
    assert result[0]['event'] == 'ADD'
    assert result[0]['memory'] == 'New memory added.'


def test_add_memory_invalid_json(memory_instance):
    memory_instance.llm.generate_response = Mock(return_value='{"memory": [{"event": "ADD", "text": "New memory added."}')
    memory_instance.remove_code_blocks = Mock(return_value='{"memory": [{"event": "ADD", "text": "New memory added."}')

    with pytest.raises(Exception):
        memory_instance.add(messages="Test message", user_id="user1")


def test_add_memory_empty_response(memory_instance):
    memory_instance.llm.generate_response = Mock(return_value='{"memory": []}')
    memory_instance.remove_code_blocks = Mock(return_value='{"memory": []}')

    result = memory_instance.add(messages="Test message", user_id="user1")

    assert result == []
