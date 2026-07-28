"""Project-level configuration: the write gate, the taxonomy, and the lifecycle toggle.

This module is the single source of truth for how the platform is configured. The
custom instructions ARE the write gate -- they were validated against the real
polluted v1 corpus (see eval/fixtures.py) and suppress every mechanical-noise class.

Bump POLICY_VERSION whenever INSTRUCTIONS or CATEGORIES change; it is stamped onto
every memory's metadata so quality regressions can be traced to a policy revision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

POLICY_VERSION = "v2.0"

# The six memory types. This enum is authoritative for both metadata.type (used at
# read time, available immediately) and the platform's custom categories (assigned
# by the classifier hours later, used as a secondary signal).
TYPES: tuple[str, ...] = (
    "preference",
    "decision",
    "convention",
    "insight",
    "runbook",
    "session_state",
)

# Types that make up the durable knowledge base. session_state is excluded: it is
# session-scoped, short-lived, and retrieved by its own recipe.
DURABLE_TYPES: tuple[str, ...] = (
    "preference",
    "decision",
    "convention",
    "insight",
    "runbook",
)

# Types stored at user scope (null app_id) rather than project scope.
USER_SCOPED_TYPES: frozenset[str] = frozenset({"preference"})

# Days until a session_state record stops surfacing. Expiration hides, never deletes.
SESSION_STATE_TTL_DAYS = 14


INSTRUCTIONS = """Your Task: Extract durable knowledge from a developer's session with a coding assistant.
A fact qualifies ONLY if it would change how an assistant behaves in a future session.

Information to Extract:
1. preference - how the developer wants work done: style, workflow, tools, communication, review habits.
2. decision - a resolved technical choice AND the reasoning behind it.
3. convention - a project or team rule that is not written in the repository docs.
4. insight - a root-caused gotcha, constraint, or non-obvious behavior of the system.
5. runbook - a multi-step procedure that was verified to work end to end.

Guidelines:
- One self-contained fact per memory, understandable without the conversation.
- State the general lesson, not the incident that revealed it.
- Attribute correctly: the assistant's own observations are NOT the user's preferences.
- Include the reasoning for decisions when it was stated.

Exclude (never store):
- Progress updates, status heartbeats, ETAs, percentages, epochs, task notifications, monitoring output, training or job metrics
- Anything the assistant merely did, said, asked, or planned in the middle of a task
- Lists of files modified, commits made, or PRs opened, and other activity derivable from git
- Contents of repository files such as CLAUDE.md, README, or configs
- Anything true only for the current session or the current run
- One-off instructions that apply only to the task at hand ("you do it", "run it yourself this time", "skip tests for now"); store a preference only when it is stated as a general or recurring rule
- Secrets, API keys, tokens, credentials, connection strings
"""


CATEGORIES: list[dict[str, str]] = [
    {"preference": "How this developer wants work done: coding style, workflow, tooling, communication and review habits"},
    {"decision": "A resolved technical choice and the reasoning behind it; superseded when the choice is reversed"},
    {"convention": "A project or team rule that is not documented in the repository itself"},
    {"insight": "A root-caused gotcha, constraint, or non-obvious behavior of the system or its tooling"},
    {"runbook": "A verified multi-step procedure such as deploying, debugging, setting up, or releasing"},
    {"session_state": "Open-thread snapshot for a single session: current goal, status, blockers, next step"},
]


@dataclass
class ConfigReport:
    """Outcome of applying project configuration, with a verified round-trip."""

    applied: list[str] = field(default_factory=list)
    failed: list[tuple[str, Any]] = field(default_factory=list)
    verified: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        if self.failed:
            return False
        cats = self.verified.get("custom_categories") or []
        names = [next(iter(c)) for c in cats if isinstance(c, dict)]
        return (
            bool(self.verified.get("custom_instructions"))
            and set(names) == set(TYPES)
            and self.verified.get("decay") is True
        )

    def summary(self) -> str:
        state = "ok" if self.ok else "incomplete"
        return (
            f"project config {state}: applied={','.join(self.applied) or 'none'}"
            + (f" failed={self.failed}" if self.failed else "")
        )


def apply_project_config(api, *, project_id: str | None = None) -> ConfigReport:
    """Idempotently push instructions, categories and decay, then verify by reading back.

    Safe to call on every onboard. `api` is a mem0_agent.api.Api instance.
    """
    report = ConfigReport()
    updates = {
        "custom_instructions": {"custom_instructions": INSTRUCTIONS},
        "custom_categories": {"custom_categories": CATEGORIES},
        "decay": {"decay": True},
    }
    for name, payload in updates.items():
        status, body = api.project_update(project_id=project_id, **payload)
        if status == 200:
            report.applied.append(name)
        else:
            report.failed.append((name, body))

    # Verified behavior: `fields` must be sent as repeated query params, not comma-joined.
    status, body = api.project_get(
        project_id=project_id, fields=["custom_instructions", "custom_categories", "decay"]
    )
    if status == 200 and isinstance(body, dict):
        report.verified = body
    else:
        report.failed.append(("verify", body))
    return report
