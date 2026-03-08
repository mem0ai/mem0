"""Configuration types and defaults for Claude Code mem0 integration."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class ProjectConfig:
    """Project-specific configuration for mem0 hooks.

    Each project (e.g., Mister-Smith) provides its own config
    with domain-specific instructions and categories.
    """

    # Entity scoping
    user_id: str
    app_id: str
    agent_id_main: str = "claude-code"
    agent_id_subagent: str = "claude-code-subagent"
    agent_id_bootstrap: str = "bootstrap"

    # Extraction control
    custom_instructions: str = ""
    custom_categories: List[Dict[str, str]] = field(default_factory=list)
    includes: str = ""
    excludes: str = ""

    # Capture thresholds
    capture_min_chars: int = 50
    subagent_min_chars: int = 100
    max_capture_chars: int = 8000

    # Recall settings
    recall_top_k: int = 5
    session_recall_top_k: int = 3
    startup_top_k: int = 10

    # Expiration tiers (days)
    auto_capture_expiry_days: Optional[int] = 30  # Normal auto-captures
    compact_expiry_days: int = 7  # Pre-compact ephemeral
    # Seeds and immutable memories: no expiration (None)

    # Prompt filtering
    skip_prompts: Set[str] = field(
        default_factory=lambda: {
            "yes", "no", "y", "n", "continue", "ok",
            "done", "stop", "exit", "quit",
        }
    )
