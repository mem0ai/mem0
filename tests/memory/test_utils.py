import re
from mem0.memory.utils import extract_json, remove_code_blocks

def test_remove_code_blocks():
    # Test thinking tags
    assert remove_code_blocks("<think>abc</think>\ncontent") == "content"
    
    # Test code block extraction (nested or with preamble)
    assert remove_code_blocks("Here is code: ```python\nprint(1)\n```") == "print(1)"
    
    # Test no code block
    assert remove_code_blocks("plain text") == "plain text"

def test_extract_json_robustness():
    # Scenario: Raw JSON
    raw = '{"facts": ["fact1"]}'
    assert extract_json(raw) == raw
    
    # Scenario: JSON in Markdown
    markdown = '```json\n{"facts": ["fact1"]}\n```'
    assert extract_json(markdown) == '{"facts": ["fact1"]}'
    
    # Scenario: JSON with Preamble and Postamble
    noisy = 'Text before\n{"facts": ["fact1"]}\nText after'
    assert extract_json(noisy) == '{"facts": ["fact1"]}'
    
    # Scenario: Markdown JSON with Preamble
    noisy_markdown = 'Sure! ```json\n{"facts": ["fact1"]}\n``` done.'
    assert extract_json(noisy_markdown) == '{"facts": ["fact1"]}'

if __name__ == "__main__":
    # Manual execution if needed
    test_remove_code_blocks()
    test_extract_json_robustness()
    print("Test Utils: OK")
