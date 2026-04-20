from mem0.memory.utils import extract_json, remove_code_blocks


def test_remove_code_blocks_handles_think_tags_and_wrapped_blocks():
    assert remove_code_blocks("<think>abc</think>\ncontent") == "content"
    assert remove_code_blocks("Here is code: ```python\nprint(1)\n```") == "print(1)"
    assert remove_code_blocks("plain text") == "plain text"


def test_extract_json_handles_raw_markdown_and_noisy_wrappers():
    raw = '{"facts": ["fact1"]}'
    markdown = '```json\n{"facts": ["fact1"]}\n```'
    noisy = 'Text before\n{"facts": ["fact1"]}\nText after'
    noisy_markdown = 'Sure! ```json\n{"facts": ["fact1"]}\n``` done.'

    assert extract_json(raw) == raw
    assert extract_json(markdown) == '{"facts": ["fact1"]}'
    assert extract_json(noisy) == '{"facts": ["fact1"]}'
    assert extract_json(noisy_markdown) == '{"facts": ["fact1"]}'
