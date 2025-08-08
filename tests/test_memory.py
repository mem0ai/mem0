from unittest.mock import MagicMock, patch

import pytest

from mem0 import Memory


@pytest.fixture
def memory_client():
    with patch.object(Memory, "__init__", return_value=None):
        client = Memory()
        client.add = MagicMock(return_value={"results": [{"id": "1", "memory": "Name is John Doe.", "event": "ADD"}]})
        client.get = MagicMock(return_value={"id": "1", "memory": "Name is John Doe."})
        client.update = MagicMock(return_value={"message": "Memory updated successfully!"})
        client.delete = MagicMock(return_value={"message": "Memory deleted successfully!"})
        client.history = MagicMock(return_value=[{"memory": "I like Indian food."}, {"memory": "I like Italian food."}])
        client.get_all = MagicMock(return_value=["Name is John Doe.", "Name is John Doe. I like to code in Python."])
        yield client


def test_create_memory(memory_client):
    data = "Name is John Doe."
    result = memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    assert result["results"][0]["memory"] == data


def test_get_memory(memory_client):
    data = "Name is John Doe."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    result = memory_client.get("1")
    assert result["memory"] == data


def test_update_memory(memory_client):
    data = "Name is John Doe."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    new_data = "Name is John Kapoor."
    update_result = memory_client.update("1", text=new_data)
    assert update_result["message"] == "Memory updated successfully!"


def test_delete_memory(memory_client):
    data = "Name is John Doe."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    delete_result = memory_client.delete("1")
    assert delete_result["message"] == "Memory deleted successfully!"


def test_history(memory_client):
    data = "I like Indian food."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    memory_client.update("1", text="I like Italian food.")
    history = memory_client.history("1")
    assert history[0]["memory"] == "I like Indian food."
    assert history[1]["memory"] == "I like Italian food."


def test_list_memories(memory_client):
    data1 = "Name is John Doe."
    data2 = "Name is John Doe. I like to code in Python."
    memory_client.add([{"role": "user", "content": data1}], user_id="test_user")
    memory_client.add([{"role": "user", "content": data2}], user_id="test_user")
    memories = memory_client.get_all(user_id="test_user")
    assert data1 in memories
    assert data2 in memories
