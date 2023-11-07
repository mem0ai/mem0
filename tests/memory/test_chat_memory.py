import pytest

from embedchain.memory.base import ECChatMemory
from embedchain.memory.message import ChatMessage


# Fixture for creating an instance of ECChatMemory
@pytest.fixture
def chat_memory_instance():
    return ECChatMemory()


def test_add_chat_memory(chat_memory_instance):
    app_id = "test_app"
    human_message = "Hello, how are you?"
    ai_message = "I'm fine, thank you!"

    chat_message = ChatMessage()
    chat_message.add_user_message(human_message)
    chat_message.add_ai_message(ai_message)

    chat_memory_instance.add(app_id, chat_message)

    assert chat_memory_instance.count_history_messages(app_id) == 1
    chat_memory_instance.delete_chat_history(app_id)


def test_get_recent_memories(chat_memory_instance):
    app_id = "test_app"

    for i in range(1, 7):
        human_message = f"Question {i}"
        ai_message = f"Answer {i}"

        chat_message = ChatMessage()
        chat_message.add_user_message(human_message)
        chat_message.add_ai_message(ai_message)

        chat_memory_instance.add(app_id, chat_message)

    recent_memories = chat_memory_instance.get_recent_memories(app_id, num_rounds=5)

    assert len(recent_memories) == 5


def test_delete_chat_history(chat_memory_instance):
    app_id = "test_app"

    for i in range(1, 6):
        human_message = f"Question {i}"
        ai_message = f"Answer {i}"

        chat_message = ChatMessage()
        chat_message.add_user_message(human_message)
        chat_message.add_ai_message(ai_message)

        chat_memory_instance.add(app_id, chat_message)

    chat_memory_instance.delete_chat_history(app_id)

    assert chat_memory_instance.count_history_messages(app_id) == 0


@pytest.fixture
def close_connection(chat_memory_instance):
    yield
    chat_memory_instance.close_connection()
