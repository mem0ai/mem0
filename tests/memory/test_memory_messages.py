from embedchain.memory.message import BaseMessage, ChatMessage


def test_ec_base_message():
    content = "Hello, how are you?"
    created_by = "human"
    metadata = {"key": "value"}

    message = BaseMessage(content=content, created_by=created_by, metadata=metadata)

    assert message.content == content
    assert message.created_by == created_by
    assert message.metadata == metadata
    assert message.type is None
    assert message.is_lc_serializable() is True
    assert str(message) == f"{created_by}: {content}"


def test_ec_base_chat_message():
    human_message_content = "Hello, how are you?"
    ai_message_content = "I'm fine, thank you!"
    human_metadata = {"user": "John"}
    ai_metadata = {"response_time": 0.5}

    chat_message = ChatMessage()
    chat_message.add_user_message(human_message_content, metadata=human_metadata)
    chat_message.add_ai_message(ai_message_content, metadata=ai_metadata)

    assert chat_message.human_message.content == human_message_content
    assert chat_message.human_message.created_by == "human"
    assert chat_message.human_message.metadata == human_metadata

    assert chat_message.ai_message.content == ai_message_content
    assert chat_message.ai_message.created_by == "ai"
    assert chat_message.ai_message.metadata == ai_metadata

    assert str(chat_message) == f"human: {human_message_content}\nai: {ai_message_content}"
