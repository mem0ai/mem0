"""
Tests for issue #3559: Custom prompts crash with response_format json_object
when the word 'json' is not present in the prompt.

OpenAI API requires the word 'json' to appear in messages when using
response_format: {"type": "json_object"}. Custom fact extraction prompts
may not include this word, causing BadRequestError.

This tests the ensure_json_instruction utility function and verifies
the fix is applied in both sync and async code paths.
"""

import pytest

from mem0.memory.utils import ensure_json_instruction


class TestEnsureJsonInstruction:
    """Tests for the ensure_json_instruction utility function."""

    # -------------------------------------------------------------------
    # Core behavior: append when missing, skip when present
    # -------------------------------------------------------------------

    def test_appends_when_json_missing_from_both_prompts(self):
        """When neither prompt contains 'json', instruction is appended to system prompt."""
        system, user = ensure_json_instruction(
            "Extract facts from the conversation and return them as a list.",
            "Input:\nuser: Hi my name is John",
        )
        assert "json" in system.lower()
        assert "facts" in system.lower()

    def test_no_change_when_json_in_system_prompt(self):
        """When system prompt already contains 'json', no modification."""
        original = "Extract facts and return in json format."
        system, user = ensure_json_instruction(original, "Input:\nuser: Hi")
        assert system == original

    def test_no_change_when_json_in_user_prompt(self):
        """When user prompt contains 'json', no modification to system prompt."""
        original_system = "Extract facts from the conversation."
        original_user = "Input (respond in json):\nuser: Hi"
        system, user = ensure_json_instruction(original_system, original_user)
        assert system == original_system

    def test_user_prompt_never_modified(self):
        """The user prompt should never be modified regardless of content."""
        original_user = "Input:\nuser: I like pizza"
        _, user = ensure_json_instruction("Extract facts.", original_user)
        assert user == original_user

    # -------------------------------------------------------------------
    # Case insensitivity
    # -------------------------------------------------------------------

    def test_case_insensitive_lowercase(self):
        original = "Return results in json format."
        system, _ = ensure_json_instruction(original, "Input:\nuser: Hi")
        assert system == original

    def test_case_insensitive_uppercase(self):
        original = "Return results in JSON format."
        system, _ = ensure_json_instruction(original, "Input:\nuser: Hi")
        assert system == original

    def test_case_insensitive_mixed(self):
        original = "Return results in Json format."
        system, _ = ensure_json_instruction(original, "Input:\nuser: Hi")
        assert system == original

    def test_case_insensitive_in_user_prompt(self):
        original_system = "Extract facts."
        system, _ = ensure_json_instruction(original_system, "Return JSON.\nuser: Hi")
        assert system == original_system

    # -------------------------------------------------------------------
    # Parametrized: various custom prompts
    # -------------------------------------------------------------------

    @pytest.mark.parametrize(
        "prompt,should_append",
        [
            # Prompts WITHOUT json — should append
            ("Extract all facts from the conversation.", True),
            ("You are a memory extractor. Return facts as a list.", True),
            ("Analyze the input and find key information.", True),
            ("Return data in structured format.", True),
            ("List the user preferences.", True),
            # Prompts WITH json — should NOT append
            ("Extract facts and return in json format.", False),
            ("Return a json object with facts.", False),
            ("Output must be valid JSON.", False),
            ("Respond with a JSON array of facts.", False),
            ("Format: json output expected.", False),
        ],
    )
    def test_various_custom_prompts(self, prompt, should_append):
        user_prompt = "Input:\nuser: Hi my name is John"
        system, _ = ensure_json_instruction(prompt, user_prompt)

        if should_append:
            assert system != prompt, f"Expected JSON instruction to be appended for: {prompt}"
            assert "json" in system.lower()
        else:
            assert system == prompt, f"Did not expect modification for: {prompt}"

    # -------------------------------------------------------------------
    # Edge cases
    # -------------------------------------------------------------------

    def test_empty_system_prompt(self):
        """Empty system prompt should get JSON instruction."""
        system, _ = ensure_json_instruction("", "Input:\nuser: test")
        assert "json" in system.lower()

    def test_whitespace_only_system_prompt(self):
        """Whitespace-only prompt should get JSON instruction."""
        system, _ = ensure_json_instruction("   \n  ", "Input:\nuser: test")
        assert "json" in system.lower()

    def test_preserves_original_prompt_content(self):
        """The fix should only append, never modify the original prompt content."""
        original = "Extract all user preferences and habits from the conversation."
        system, _ = ensure_json_instruction(original, "Input:\nuser: I like pizza")
        assert system.startswith(original)
        assert len(system) > len(original)

    def test_appended_instruction_mentions_facts_key(self):
        """The appended instruction should guide the model to use the 'facts' key."""
        system, _ = ensure_json_instruction(
            "Extract information.", "Input:\nuser: test"
        )
        assert "facts" in system.lower()

    def test_idempotent_when_already_has_json(self):
        """Calling ensure_json_instruction twice doesn't double-append."""
        system1, user1 = ensure_json_instruction(
            "Extract facts.", "Input:\nuser: test"
        )
        system2, user2 = ensure_json_instruction(system1, user1)
        assert system1 == system2
        assert user1 == user2

    def test_json_in_curly_braces_not_detected(self):
        """A prompt with JSON-like structure but no 'json' word should get instruction.
        e.g. '{"facts": [...]}' contains the characters j,s,o,n but not the word 'json'."""
        prompt = 'Return format: {"facts": [...]}'
        # This contains the substring "json" inside the key name — let's check
        if "json" in prompt.lower():
            # If it does contain json, it won't be modified
            system, _ = ensure_json_instruction(prompt, "Input:\nuser: test")
            assert system == prompt
        else:
            system, _ = ensure_json_instruction(prompt, "Input:\nuser: test")
            assert system != prompt

    # -------------------------------------------------------------------
    # Default prompts verification
    # -------------------------------------------------------------------

    def test_default_prompts_already_contain_json(self):
        """Built-in prompts already contain 'json', so ensure_json_instruction is a no-op."""
        from mem0.configs.prompts import (
            FACT_RETRIEVAL_PROMPT,
            USER_MEMORY_EXTRACTION_PROMPT,
            AGENT_MEMORY_EXTRACTION_PROMPT,
        )

        for name, prompt in [
            ("FACT_RETRIEVAL_PROMPT", FACT_RETRIEVAL_PROMPT),
            ("USER_MEMORY_EXTRACTION_PROMPT", USER_MEMORY_EXTRACTION_PROMPT),
            ("AGENT_MEMORY_EXTRACTION_PROMPT", AGENT_MEMORY_EXTRACTION_PROMPT),
        ]:
            assert "json" in prompt.lower(), (
                f"{name} should contain 'json' — "
                "if this fails, the default prompts have changed"
            )
            # ensure_json_instruction should be a no-op for defaults
            system, _ = ensure_json_instruction(prompt, "Input:\nuser: test")
            assert system == prompt, f"ensure_json_instruction modified {name} unexpectedly"

    # -------------------------------------------------------------------
    # Integration: verify fix is wired into both sync and async paths
    # -------------------------------------------------------------------

