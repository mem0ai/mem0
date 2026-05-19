from mem0.memory.utils import parse_vision_messages


def test_list_content_passes_through_when_llm_is_none():
    """parse_vision_messages must not crash when llm=None and content is a list.

    Regression test for #4799: Memory.add() calls parse_vision_messages without
    an LLM when enable_vision=False (the default). Previously, list-typed content
    triggered get_image_description() which called llm.generate_response() on a
    None object, raising AttributeError.
    """
    messages = [{"role": "user", "content": [{"type": "text", "text": "I love hiking"}]}]
    result = parse_vision_messages(messages, llm=None)
    assert result == messages


def test_image_url_dict_content_passes_through_when_llm_is_none():
    """parse_vision_messages must not crash when llm=None and content is an image_url dict."""
    messages = [
        {
            "role": "user",
            "content": {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
        }
    ]
    result = parse_vision_messages(messages, llm=None)
    assert result == messages


def test_plain_text_content_passes_through_unchanged():
    """Plain text messages are unaffected by the fix."""
    messages = [{"role": "user", "content": "Hello world"}]
    result = parse_vision_messages(messages, llm=None)
    assert result == messages


def test_system_message_passes_through_unchanged():
    """System messages are always returned as-is regardless of llm."""
    messages = [{"role": "system", "content": "You are helpful."}]
    result = parse_vision_messages(messages, llm=None)
    assert result == messages


def test_mixed_messages_with_null_llm():
    """Mix of system, plain text, list-content, and image_url-dict all pass through when llm=None."""
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "plain text"},
        {"role": "user", "content": [{"type": "text", "text": "list content"}]},
        {
            "role": "user",
            "content": {"type": "image_url", "image_url": {"url": "https://example.com/x.png"}},
        },
    ]
    result = parse_vision_messages(messages, llm=None)
    assert result == messages
