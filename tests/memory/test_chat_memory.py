import pytest

from embedchain.memory.base import ChatHistory
from embedchain.memory.message import ChatMessage


# Fixture for creating an instance of ChatHistory
@pytest.fixture
def chat_memory_instance():
    return ChatHistory()


def test_add_chat_memory(chat_memory_instance):
    app_id = "test_app"
    session_id = "test_session"
    human_message = "Hello, how are you?"
    ai_message = "I'm fine, thank you!"

    chat_message = ChatMessage()
    chat_message.add_user_message(human_message)
    chat_message.add_ai_message(ai_message)

    chat_memory_instance.add(app_id, session_id, chat_message)

    assert chat_memory_instance.count(app_id, session_id) == 1
    chat_memory_instance.delete(app_id, session_id)


def test_get(chat_memory_instance):
    app_id = "test_app"
    session_id = "test_session"

    for i in range(1, 7):
        human_message = f"Question {i}"
        ai_message = f"Answer {i}"

        chat_message = ChatMessage()
        chat_message.add_user_message(human_message)
        chat_message.add_ai_message(ai_message)

        chat_memory_instance.add(app_id, session_id, chat_message)

    recent_memories = chat_memory_instance.get(app_id, session_id, num_rounds=5)

    assert len(recent_memories) == 5

    all_memories = chat_memory_instance.get(app_id, fetch_all=True)

    assert len(all_memories) == 6


def test_delete_chat_history(chat_memory_instance):
    app_id = "test_app"
    session_id = "test_session"

    for i in range(1, 6):
        human_message = f"Question {i}"
        ai_message = f"Answer {i}"

        chat_message = ChatMessage()
        chat_message.add_user_message(human_message)
        chat_message.add_ai_message(ai_message)

        chat_memory_instance.add(app_id, session_id, chat_message)

    session_id_2 = "test_session_2"

    for i in range(1, 6):
        human_message = f"Question {i}"
        ai_message = f"Answer {i}"

        chat_message = ChatMessage()
        chat_message.add_user_message(human_message)
        chat_message.add_ai_message(ai_message)

        chat_memory_instance.add(app_id, session_id_2, chat_message)

    chat_memory_instance.delete(app_id, session_id)

    assert chat_memory_instance.count(app_id, session_id) == 0
    assert chat_memory_instance.count(app_id) == 5

    chat_memory_instance.delete(app_id)

    assert chat_memory_instance.count(app_id) == 0


@pytest.fixture
def close_connection(chat_memory_instance):
    yield
    chat_memory_instance.close_connection()
