"""One object every hook builds: credentials, identity, scope, API, state."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .api import Api
from .breaker import Breaker
from .settings import (
    SessionState,
    Settings,
    get_api_key,
    resolve_app_id,
    resolve_branch,
    resolve_user_id,
)


@dataclass
class Ctx:
    api: Optional[Api]
    settings: Settings
    state: SessionState
    user_id: str
    app_id: str
    session_id: str
    branch: str | None
    ready: bool
    reason: str = ""

    @property
    def editor(self) -> str:
        return os.environ.get("MEM0_EDITOR", "claude-code")

    def provenance(self, mtype: str) -> dict:
        """Metadata stamped on every write. `type` is what reads filter on -- platform
        categories arrive hours later and cannot be relied on at read time."""
        from .config.project_config import POLICY_VERSION

        meta = {
            "type": mtype,
            "session_id": self.session_id,
            "editor": self.editor,
            "policy": POLICY_VERSION,
        }
        if self.branch:
            meta["branch"] = self.branch
        return meta

    def log(self, event: str, **fields) -> None:
        self.state.append("events.jsonl", {"event": event, **fields})


def build(session_id: str | None = None, cwd: str | None = None, *, strict: bool = False) -> Ctx:
    """Never raises. If anything is missing, returns ready=False and the caller no-ops."""
    session_id = session_id or os.environ.get("MEM0_SESSION_ID") or "no-session"
    settings = Settings.load()
    state = SessionState(session_id)
    key = get_api_key()
    if not key:
        return Ctx(None, settings, state, "", "", session_id, None, False, "no API key")

    # An API key is already bound to one (org, project) on the backend, so neither id is
    # required here. They are sent only to OVERRIDE that binding -- i.e. to point one key at
    # a different project in the same org. Left unset, every call resolves server-side.
    org = settings.get("org_id") or os.environ.get("MEM0_AGENT_ORG_ID")
    project = settings.get("memory_project_id") or os.environ.get("MEM0_AGENT_PROJECT_ID")
    api = Api(key, org_id=org, project_id=project,
              breaker=Breaker(state.breaker_path), strict=strict)

    # An override needs both halves; one alone would be ignored and quietly mislead.
    if bool(org) != bool(project):
        api.org_id = api.project_id = None
        settings_warning = "project override ignored: set both org_id and memory_project_id"
    else:
        settings_warning = ""

    user_id = resolve_user_id(api, settings)
    app_id = resolve_app_id(cwd, settings)
    branch = resolve_branch(cwd)
    return Ctx(api, settings, state, user_id, app_id, session_id, branch, True, settings_warning)
