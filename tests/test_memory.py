import pytest

from mem0 import Memory


@pytest.fixture
def memory_store():
    return Memory()


def test_create_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    assert memory_store.get(memory_id) == data


def test_get_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    retrieved_data = memory_store.get(memory_id)
    assert retrieved_data == data


def test_update_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    new_data = "Name is John Kapoor."
    updated_memory = memory_store.update(memory_id, new_data)
    assert updated_memory == new_data
    assert memory_store.get(memory_id) == new_data


def test_delete_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    memory_store.delete(memory_id)
    assert memory_store.get(memory_id) is None


def test_history(memory_store):
    data = "I like indian food."
    memory_id = memory_store.create(data=data)
    history = memory_store.history(memory_id)
    assert history == [data]
    assert memory_store.get(memory_id) == data

    new_data = "I like italian food."
    memory_store.update(memory_id, new_data)
    history = memory_store.history(memory_id)
    assert history == [data, new_data]
    assert memory_store.get(memory_id) == new_data


def test_list_memories(memory_store):
    data1 = "Name is John Doe."
    data2 = "Name is John Doe. I like to code in Python."
    memory_store.create(data=data1)
    memory_store.create(data=data2)
    memories = memory_store.list()
    assert data1 in memories
    assert data2 in memories
