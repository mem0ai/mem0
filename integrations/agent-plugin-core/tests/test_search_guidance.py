"""Keep optional retrieval guidance consistent across the Python and TS hosts."""

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS = ROOT.parent


def test_python_and_typescript_share_the_same_search_guidance():
    tree = ast.parse((ROOT / "python/mcp_server.py").read_text())
    guidance = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "SEARCH_GUIDANCE" for t in node.targets)
    )
    typescript = (ROOT / "typescript/src/search_guidance.ts").read_text()
    ts_guidance = "".join(json.loads(value) for value in re.findall(r'"(?:[^"\\]|\\.)*"', typescript))
    assert guidance == ts_guidance
    assert "skip another search when the context already answers it" in guidance
    assert "Search again only if a specific gap remains" in guidance
    for relative in (
        "opencode-plugin/opencode-mem0.ts",
        "pi-agent-plugin/src/prompt.ts",
        "pi-agent-plugin/src/memory/tools.ts",
        "openclaw/tools/memory-search.ts",
        "openclaw/skill-loader.ts",
        "deepseek-plugin/src/index.ts",
    ):
        source = (INTEGRATIONS / relative).read_text()
        assert 'import {SEARCH_GUIDANCE}' in source or 'import { SEARCH_GUIDANCE }' in source, relative
        assert source.count("SEARCH_GUIDANCE") >= 2, relative


def test_prompts_do_not_require_speculative_or_repeated_searches():
    sources = [ROOT / "python/mcp_server.py", ROOT / "skills/search/SKILL.md.tmpl"]
    for plugin in (
        "claude-code-plugin", "cursor-plugin", "codex-plugin", "kimi-plugin", "antigravity-plugin",
        "opencode-plugin", "pi-agent-plugin", "openclaw", "deepseek-plugin",
    ):
        for path in (INTEGRATIONS / plugin).rglob("*"):
            if {"node_modules", "dist", "core"} & set(path.parts) or ".test." in path.name:
                continue
            if path.suffix in {".md", ".ts"} and path.name != "README.md":
                sources.append(path)
    strict = re.compile(
        r"always call .{0,35}search|search memory before answering|proactively before answering|"
        r"multi-hop|run (?:2-4|2|several) (?:parallel )?(?:`search_memories` calls|searches)|"
        r"one search is rarely enough|always rewrite the query",
        re.IGNORECASE,
    )
    for path in sources:
        assert not strict.search(" ".join(path.read_text().split())), path
