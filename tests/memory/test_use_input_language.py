"""Verify MemoryConfig.use_input_language propagates into the extraction prompt."""

from mem0.configs.base import MemoryConfig
from mem0.configs.prompts import generate_additive_extraction_prompt


def test_flag_defaults_to_false():
    cfg = MemoryConfig()
    assert cfg.use_input_language is False


def test_flag_off_omits_language_requirement():
    prompt = generate_additive_extraction_prompt(
        existing_memories=[],
        new_messages=[{"role": "user", "content": "I like apples"}],
        last_k_messages=[],
        use_input_language=False,
    )
    assert "## Language Requirement" not in prompt


def test_flag_on_injects_language_requirement():
    cfg = MemoryConfig(use_input_language=True)
    prompt = generate_additive_extraction_prompt(
        existing_memories=[],
        new_messages=[{"role": "user", "content": "我叫小明"}],
        last_k_messages=[],
        use_input_language=cfg.use_input_language,
    )
    assert "## Language Requirement" in prompt
    assert "SAME LANGUAGE and SCRIPT" in prompt
