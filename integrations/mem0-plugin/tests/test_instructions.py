"""Tests for the mem0.md extraction-policy feature.

Covers the parser (`parse_section_text` + the Instructions sections in
`load_full_config`) and the `_instructions.load_instructions` helper that the
hook writers use to attach `custom_instructions` / `agent_custom_instructions`
to a memory write.
"""

from __future__ import annotations

MEM0_MD = """\
# mem0.md

## Categories
- architecture_decisions

## Instructions
Remember architecture decisions and conventions.
Ignore transient debug output and secrets (issue #123 refs are fine).

## Agent Instructions
For agent memories, focus on tools and task outcomes.
"""


# ---------------------------------------------------------------------------
# parse_section_text
# ---------------------------------------------------------------------------


def test_parse_section_text_collapses_prose():
    from parse_mem0_config import parse_section_text

    text = parse_section_text(MEM0_MD, "Instructions")
    assert text == (
        "Remember architecture decisions and conventions. "
        "Ignore transient debug output and secrets (issue #123 refs are fine)."
    )


def test_parse_section_text_preserves_inline_hash():
    """Inline '#' (e.g. issue refs) is kept; only full-line comments are dropped."""
    from parse_mem0_config import parse_section_text

    assert "#123" in parse_section_text(MEM0_MD, "Instructions")


def test_instructions_and_agent_instructions_are_distinct():
    """'## Instructions' must not swallow '## Agent Instructions'."""
    from parse_mem0_config import parse_section_text

    assert parse_section_text(MEM0_MD, "Instructions").startswith("Remember architecture")
    assert parse_section_text(MEM0_MD, "Agent Instructions") == (
        "For agent memories, focus on tools and task outcomes."
    )


def test_parse_section_text_missing_returns_empty():
    from parse_mem0_config import parse_section_text

    assert parse_section_text("## Retention\nx: 1d\n", "Instructions") == ""


def test_load_full_config_includes_instructions(tmp_path):
    from parse_mem0_config import load_full_config

    (tmp_path / "mem0.md").write_text(MEM0_MD)
    config = load_full_config(str(tmp_path))
    assert config["instructions"].startswith("Remember architecture")
    assert config["agent_instructions"].startswith("For agent memories")


# ---------------------------------------------------------------------------
# load_instructions (the helper the hook writers call)
# ---------------------------------------------------------------------------


def test_load_instructions_maps_to_api_field_names(tmp_path):
    from _instructions import load_instructions

    (tmp_path / "mem0.md").write_text(MEM0_MD)
    out = load_instructions(str(tmp_path))
    assert out == {
        "custom_instructions": (
            "Remember architecture decisions and conventions. "
            "Ignore transient debug output and secrets (issue #123 refs are fine)."
        ),
        "agent_custom_instructions": "For agent memories, focus on tools and task outcomes.",
    }


def test_load_instructions_no_config_is_empty(tmp_path):
    """No mem0.md -> empty dict, so a write body gains nothing."""
    from _instructions import load_instructions

    assert load_instructions(str(tmp_path)) == {}


def test_load_instructions_only_custom(tmp_path):
    """A project with only '## Instructions' omits the agent key entirely."""
    from _instructions import load_instructions

    (tmp_path / "mem0.md").write_text("## Instructions\nRemember decisions.\n")
    out = load_instructions(str(tmp_path))
    assert out == {"custom_instructions": "Remember decisions."}


def test_load_instructions_defaults_cwd_to_env(tmp_path, monkeypatch):
    """With no arg, cwd falls back to MEM0_CWD."""
    from _instructions import load_instructions

    (tmp_path / "mem0.md").write_text("## Instructions\nRemember decisions.\n")
    monkeypatch.setenv("MEM0_CWD", str(tmp_path))
    assert load_instructions() == {"custom_instructions": "Remember decisions."}


def test_load_instructions_body_merge_shape(tmp_path):
    """The result merges cleanly into an add body without clobbering other keys."""
    from _instructions import load_instructions

    (tmp_path / "mem0.md").write_text("## Instructions\nRemember decisions.\n")
    body = {"messages": [], "user_id": "u", "infer": True}
    body.update(load_instructions(str(tmp_path)))
    assert body["user_id"] == "u" and body["infer"] is True
    assert body["custom_instructions"] == "Remember decisions."
    assert "agent_custom_instructions" not in body
