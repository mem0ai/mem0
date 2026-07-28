"""First-run setup: credentials, scope, project config, and the memory-mode decision.

Three things v1 got wrong and this module refuses to repeat:

* v1 hunted for the API key by grepping ~/.zshrc and ~/.bashrc, then wrote it back into
  a .env file inside the repo. Here the key comes from the environment or the OS
  keychain, and a key typed at the prompt goes into the keychain and nowhere else.
* v1 assumed it owned the whole memory layer, so it fought CLAUDE.md and MEMORY.md.
  The mode question below is asked once, per project, and answered by the developer.
* v1 wrote into whatever project the API key defaulted to -- often the user's live
  production project. Onboarding now says so out loud.

Everything is non-interactive-safe: with interactive=False nothing ever blocks, and
overrides supply the answers a prompt would have.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import Any, Callable

from .config.project_config import apply_project_config
from .ctx import build
from .settings import (
    CAPTURE_LEVELS,
    MEMORY_MODES,
    RETRIEVAL_LEVELS,
    Settings,
    get_api_key,
    store_api_key,
)

# Files that mean the repo already has a memory layer of its own.
MEMORY_FILES = ("CLAUDE.md", "AGENTS.md", ".cursorrules", "MEMORY.md", ".claude/memory/")

# Above this many memories, the key's default project is doing real work already and
# coding memories do not belong in it.
BUSY_PROJECT_MEMORIES = 500

MODE_HELP = {
    "dual": (
        "DUAL  repo files stay authoritative for repo-local notes; mem0 carries durable, "
        "cross-machine knowledge. MEMORY.md write-blocker stays OFF."
    ),
    "full": (
        "FULL  mem0 is the only memory layer. MEMORY.md write-blocker ON; disable your "
        "editor's native auto-memory so the two do not both write."
    ),
}


def _repo_root(cwd: str | None = None) -> Path:
    from .settings import _git  # same git helper the rest of the package uses

    start = cwd or os.getcwd()
    return Path(_git(["rev-parse", "--show-toplevel"], start) or start)


def detect_memory_files(cwd: str | None = None) -> list[str]:
    """Which native memory files this repo already has. Existence only -- never read."""
    root = _repo_root(cwd)
    found = []
    for name in MEMORY_FILES:
        if (root / name.rstrip("/")).exists():
            found.append(name)
    return found


def _resolve_key(interactive: bool, override: str | None, secret_prompt: Callable[[str], str]) -> tuple[str | None, str]:
    """Returns (key, source). Sources: override, env, keychain, prompt, missing."""
    if override:
        return override.strip(), "override"
    if os.environ.get("MEM0_API_KEY"):
        return os.environ["MEM0_API_KEY"].strip(), "env"
    key = get_api_key()  # env already checked; this is the keychain
    if key:
        return key.strip(), "keychain"
    if not interactive:
        return None, "missing"
    typed = (secret_prompt("Mem0 API key (from https://app.mem0.ai/dashboard/api-keys): ") or "").strip()
    return (typed or None), ("prompt" if typed else "missing")


def _project_size(ctx) -> int | None:
    """Best-effort count of memories already in the target project. None = unknown."""
    for filters in ({"AND": [{"created_at": {"gte": "2000-01-01"}}]}, {"AND": [{"user_id": ctx.user_id}]}):
        try:
            status, body = ctx.api.get_all(filters, page_size=1)
        except Exception:
            continue
        if status == 200 and isinstance(body, dict) and isinstance(body.get("count"), int):
            return body["count"]
    return None


def _project_name(ctx) -> str | None:
    try:
        status, body = ctx.api.project_get(fields=["name"])
    except Exception:
        return None
    return body.get("name") if status == 200 and isinstance(body, dict) else None


def _choose_mode(interactive: bool, override: str | None, default: str,
                 prompt: Callable[[str], str], out: Callable[[str], None]) -> str:
    if override:
        mode = str(override).strip().lower()
        if mode not in MEMORY_MODES:
            raise ValueError(f"memory_mode must be one of {MEMORY_MODES}, got {override!r}")
        return mode
    if not interactive:
        return default
    out("")
    out("Memory mode for this project:")
    for mode in MEMORY_MODES:
        out(f"  {MODE_HELP[mode]}")
    answer = (prompt(f"Mode [dual/full] (default {default}): ") or "").strip().lower()
    if answer in ("d", "dual"):
        return "dual"
    if answer in ("f", "full"):
        return "full"
    return default


def run_onboard(interactive: bool = True, **overrides: Any) -> dict:
    """Set up mem0-agent for the current repo. Returns a machine-readable report.

    Overrides (all optional): api_key, memory_mode, cwd, session_id, capture, retrieval,
    prompt, secret_prompt, out.
    """
    out: Callable[[str], None] = overrides.get("out") or (lambda line: print(line))
    prompt: Callable[[str], str] = overrides.get("prompt") or input
    secret_prompt: Callable[[str], str] = overrides.get("secret_prompt") or getpass.getpass
    cwd = overrides.get("cwd")

    report: dict[str, Any] = {
        "ok": False, "api_key_source": "missing", "key_stored": False,
        "user_id": None, "app_id": None, "branch": None, "project_id": None,
        "ping_ok": False, "config": None, "config_ok": False,
        "memory_mode": None, "memory_files": [], "warnings": [], "next_steps": [],
    }

    # 1. Credentials: env -> keychain -> prompt. Never a shell rc file, never a .env.
    key, source = _resolve_key(interactive, overrides.get("api_key"), secret_prompt)
    report["api_key_source"] = source
    if not key:
        report["warnings"].append(
            "No API key. Export MEM0_API_KEY or re-run `mem0-agent onboard` interactively."
        )
        out("mem0-agent: no API key found; nothing was configured.")
        return report
    os.environ["MEM0_API_KEY"] = key  # so build() sees it even if the keychain is unavailable
    if source == "prompt":
        report["key_stored"] = store_api_key(key)
        if not report["key_stored"]:
            report["warnings"].append(
                "Key not saved: no keychain backend. `pip install 'mem0-agent[keyring]'` "
                "or export MEM0_API_KEY in your shell."
            )

    # 2. Identity and scope.
    ctx = overrides.get("ctx") or build(session_id=overrides.get("session_id") or "onboard", cwd=cwd)
    report.update(user_id=ctx.user_id or None, app_id=ctx.app_id or None, branch=ctx.branch)
    if not ctx.ready or ctx.api is None:
        report["warnings"].append(f"mem0 unreachable: {ctx.reason}. Settings were not pushed.")
        out(f"mem0-agent: {ctx.reason}; identity and project config were skipped.")
        return report
    status, _ = ctx.api.ping()
    report["ping_ok"] = status == 200
    report["project_id"] = ctx.api.project_id
    if not report["ping_ok"]:
        report["warnings"].append(f"ping failed (HTTP {status}); the key may be invalid or revoked.")

    settings: Settings = ctx.settings

    # 3. Project configuration -- the write gate lives here, so it is pushed every run.
    config = apply_project_config(ctx.api)
    report["config"] = config.summary()
    report["config_ok"] = config.ok
    if not config.ok:
        report["warnings"].append(f"{config.summary()} -- the write gate may not be active.")

    # Writing coding memories into the key's default project mixes them with whatever
    # else that project serves. Say so before it happens, not after.
    if not settings.get("memory_project_id"):
        size = _project_size(ctx)
        name = _project_name(ctx)
        busy = size is not None and size >= BUSY_PROJECT_MEMORIES
        detail = f"{size} memories" if size is not None else "size unknown"
        if busy or size is None:
            report["warnings"].append(
                f"Using the API key's default project {name or ctx.api.project_id} ({detail}). "
                "If it also serves a production app, create a dedicated coding-memory project and "
                "set `memory_project_id` in " + str(settings.path) + "."
            )

    # 4. The memory-mode decision. Default follows what the repo already does.
    files = detect_memory_files(cwd)
    report["memory_files"] = files
    default_mode = "dual" if files else "full"
    mode = _choose_mode(interactive, overrides.get("memory_mode"), default_mode, prompt, out)
    report["memory_mode"] = mode
    settings.set_project_setting(ctx.app_id, "memory_mode", mode)
    settings.set_project_setting(ctx.app_id, "block_memory_file_writes", mode == "full")
    if mode == "full":
        report["next_steps"].append(
            "Disable your editor's native auto-memory; the MEMORY.md write-blocker is now on."
        )
    elif files:
        report["next_steps"].append(
            f"Repo memory files stay authoritative: {', '.join(files)}."
        )

    # Optional dial overrides, validated so a typo cannot silently disable capture.
    for dial, allowed in (("capture", CAPTURE_LEVELS), ("retrieval", RETRIEVAL_LEVELS)):
        if overrides.get(dial):
            value = str(overrides[dial]).strip().lower()
            if value not in allowed:
                raise ValueError(f"{dial} must be one of {allowed}, got {overrides[dial]!r}")
            settings.set(dial, value)

    capture = settings.project_setting(ctx.app_id, "capture", "balanced")
    retrieval = settings.project_setting(ctx.app_id, "retrieval", "balanced")
    report["capture"] = capture
    report["retrieval"] = retrieval
    report["ok"] = bool(report["ping_ok"] and report["config_ok"])

    # 5. Summary.
    out("")
    out("mem0-agent is set up.")
    out(f"  identity   {ctx.user_id}  (key from {source})")
    out(f"  project    {ctx.app_id}" + (f" @ {ctx.branch}" if ctx.branch else ""))
    out(f"  platform   project {ctx.api.project_id} -- {report['config']}")
    out(f"  mode       {MODE_HELP[mode]}")
    out(f"  capture    {capture}   how eagerly a moment becomes a candidate memory")
    out(f"  retrieval  {retrieval}   how much context gets injected at session start")
    out("  change     mem0-agent config set capture|retrieval conservative|balanced|aggressive")
    out(f"  settings   {settings.path}")
    for warning in report["warnings"]:
        out(f"  ! {warning}")
    for step in report["next_steps"]:
        out(f"  > {step}")
    return report
