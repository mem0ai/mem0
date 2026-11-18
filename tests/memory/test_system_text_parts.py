from mem0.memory.utils import parse_vision_messages


def test_system_list_content_normalized_to_text():
    msgs = [{"role": "system", "content": [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]}]
    out = parse_vision_messages(msgs)
    assert out == [{"role": "system", "content": "hello world"}]
    # caller input untouched
    assert isinstance(msgs[0]["content"], list)


def test_system_list_without_text_skipped():
    msgs = [{"role": "system", "content": [{"type": "image_url", "image_url": {"url": "http://x/y.png"}}]}]
    assert parse_vision_messages(msgs) == []


def test_system_string_unchanged():
    msgs = [{"role": "system", "content": "plain"}]
    assert parse_vision_messages(msgs) == msgs
