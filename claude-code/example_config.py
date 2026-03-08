"""Example project configuration for mem0 Claude Code hooks.

Copy this file to your project's scripts/ directory as `mem0_config.py`
and customize the values for your project.

Usage:
    # In your hook shims:
    from mem0_config import CONFIG

    # With the CLI:
    python3 cli.py --config scripts/mem0_config.py --cwd /path/to/project stats
"""

import sys
from pathlib import Path

# Add the central library to the Python path.
# Adjust the path to wherever you cloned the mem0 repo.
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent.parent / "mem0" / "claude-code"),
)

from mem0_claude.types import ProjectConfig

CONFIG = ProjectConfig(
    # ── Entity scoping ──────────────────────────────────
    user_id="your-username",  # Your identity across all projects
    app_id="your-project",  # Isolates memories per project
    agent_id_main="claude-code",  # Main Claude Code agent
    agent_id_subagent="claude-code-subagent",  # Subagents (Explore, Plan, etc.)
    agent_id_bootstrap="bootstrap",  # Seed/setup operations
    # ── Extraction control ──────────────────────────────
    custom_instructions="""
Extract and retain:
- Key decisions and their reasoning
- Implementation patterns and conventions
- Bug patterns, root causes, and fixes
- User preferences for workflow and tools

Exclude:
- Raw code blocks longer than 10 lines
- API keys, secrets, credentials
- Recalled memories being re-injected
""",
    custom_categories=[
        {"architecture": "System design decisions and component relationships"},
        {"implementation": "Code patterns, conventions, and build configuration"},
        {"debugging": "Bug patterns, root causes, and fixes"},
        {"preferences": "User preferences, tooling choices, workflow"},
    ],
    includes="decisions, patterns, fixes, preferences",
    excludes="raw code, API keys, recalled memories",
    # ── Thresholds ──────────────────────────────────────
    capture_min_chars=50,  # Minimum message length to capture
    subagent_min_chars=100,  # Minimum subagent response to capture
    max_capture_chars=8000,  # Truncate beyond this
    # ── Recall settings ─────────────────────────────────
    recall_top_k=5,  # Long-term memories per recall
    session_recall_top_k=3,  # Session memories per recall
    startup_top_k=10,  # Memories at session start
    # ── Expiration ──────────────────────────────────────
    auto_capture_expiry_days=30,  # Auto-captures expire in 30 days
    compact_expiry_days=7,  # Pre-compact memories expire in 7 days
    # Set to None for no expiration on auto-captures
)

# Optional: seed memories for the `seed` CLI command.
# Each entry is passed to client.add() with the project's entity scoping.
SEEDS = [
    {
        "messages": [
            {
                "role": "user",
                "content": "This project uses Python 3.12 with FastAPI for the backend.",
            }
        ],
        "immutable": True,
        "infer": False,
        "metadata": {"confidence": "confirmed", "source": "architecture"},
    },
]
