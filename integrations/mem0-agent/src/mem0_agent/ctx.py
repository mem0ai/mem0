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

    org = settings.get("org_id") or os.environ.get("MEM0_ORG_ID")
    project = settings.get("memory_project_id") or settings.get("default_project_id") \
        or os.environ.get("MEM0_PLATFORM_PROJECT_ID")
    api = Api(key, org_id=org, project_id=project,
              breaker=Breaker(state.breaker_path), strict=strict)

    # First run: learn identity and the key's home project from the API itself.
    if not org or not project:
        status, body = api.ping()
        if status == 200 and isinstance(body, dict):
            api.org_id = org = body.get("org_id")
            api.project_id = project = settings.get("memory_project_id") or body.get("project_id")
            settings.set("org_id", org)
            settings.set("default_project_id", body.get("project_id"))
        else:
            return Ctx(None, settings, state, "", "", session_id, None, False, "identity unavailable")

    user_id = resolve_user_id(api, settings)
    app_id = resolve_app_id(cwd, settings)
    branch = resolve_branch(cwd)
    return Ctx(api, settings, state, user_id, app_id, session_id, branch, True)
