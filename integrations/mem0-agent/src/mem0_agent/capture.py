"""The write path: buffer flagged windows during a session, flush once at the end.

Three properties this module owes the rest of the plugin:

* Nothing is written per-turn. Hooks fire dozens of times a session; v1 called
  add() from each one and produced its duplicate storm. Candidates accumulate in
  the session state dir and go out in one batch at flush.
* Scope is decided by type, not by the caller. USER_SCOPED_TYPES (preference) are
  written WITHOUT app_id so they land at user scope and follow the developer
  between repos; everything else carries app_id.
* Writes are fire-and-forget. With infer=True the response is only
  {event_id, status: PENDING} -- extraction lands 20s-5min later, so nothing here
  ever reads a write back.

Everything fails open. A hook must never raise, never block, and never lose a
developer's session because the API had a bad minute.
"""

from __future__ import annotations

import time
from typing import Any

from .api import expiry_date, results_of
from .config import filters
from .config.project_config import SESSION_STATE_TTL_DAYS, USER_SCOPED_TYPES
from .triggers import DEFAULT_LEVEL, RECENT_SHAPE_WINDOW, TriggerResult, classify, shape_signature, turn_text

CANDIDATES_FILE = "candidates.jsonl"
SHAPES_FILE = "shapes.jsonl"
CONSUMED_FILE = "candidates.sent.jsonl"

# Roles the platform accepts on /v3/memories/add.
_WIRE_ROLES = {"user", "assistant"}


class Buffer:
    """Append-only candidate list for one session, backed by the session state dir."""

    def __init__(self, ctx):
        self.ctx = ctx

    # ---------- write ----------
    def append(self, window: list[dict], mtype: str, reason: str = "") -> None:
        self.ctx.state.append(
            CANDIDATES_FILE,
            {"window": list(window or []), "mtype": mtype, "reason": reason, "ts": time.time()},
        )

    def note_shape(self, window: list[dict]) -> None:
        self.ctx.state.append(SHAPES_FILE, {"shape": shape_signature(window), "ts": time.time()})

    # ---------- read ----------
    def pending(self) -> list[dict]:
        return self.ctx.state.read_lines(CANDIDATES_FILE)

    def recent_shapes(self, limit: int = RECENT_SHAPE_WINDOW) -> list[str]:
        rows = self.ctx.state.read_lines(SHAPES_FILE)[-limit:]
        return [r.get("shape", "") for r in rows if r.get("shape")]

    # ---------- consume ----------
    def consume(self) -> list[dict]:
        """Read the pending candidates and mark the buffer consumed.

        A second flush in the same session must not resend: the file is renamed
        aside (kept for debugging) rather than appended to.
        """
        records = self.pending()
        if not records:
            return []
        try:
            path = self.ctx.state.dir / CANDIDATES_FILE
            keep = self.ctx.state.dir / CONSUMED_FILE
            with keep.open("a") as fh:
                fh.write(path.read_text())
            path.unlink()
        except Exception:
            # Could not rotate: truncate so the records cannot be sent twice.
            try:
                (self.ctx.state.dir / CANDIDATES_FILE).write_text("")
            except Exception:
                pass
        return records


# --------------------------------------------------------------------------
# observe
# --------------------------------------------------------------------------
def observe(ctx, window: list[dict], level: str | None = None) -> TriggerResult:
    """Classify one window and buffer it when it is worth storing.

    Returns the TriggerResult so a hook can report the decision. Never raises.
    """
    if level is None:
        try:
            level = ctx.settings.project_setting(ctx.app_id, "capture", DEFAULT_LEVEL)
        except Exception:
            level = DEFAULT_LEVEL

    buf = Buffer(ctx)
    try:
        recent = buf.recent_shapes()
    except Exception:
        recent = []

    result = classify(window, level or DEFAULT_LEVEL, recent)

    try:
        buf.note_shape(window)
        if result.action == "flag" and result.mtype:
            buf.append(window, result.mtype, result.reason)
        ctx.log("capture_observe", action=result.action, mtype=result.mtype, reason=result.reason)
    except Exception:
        pass
    return result


# --------------------------------------------------------------------------
# flush
# --------------------------------------------------------------------------
def _wire_messages(window: list[dict]) -> list[dict]:
    """Reduce a window to the role/content pairs the API accepts."""
    out: list[dict] = []
    for turn in window or []:
        text = turn_text(turn).strip()
        if not text:
            continue
        role = (turn.get("role") if isinstance(turn, dict) else "") or "user"
        role = str(role).lower()
        if role in ("human",):
            role = "user"
        elif role in ("ai", "model"):
            role = "assistant"
        if role not in _WIRE_ROLES:
            role = "user"
        out.append({"role": role, "content": text})
    return out


def flush(ctx) -> dict:
    """Send every buffered candidate, then mark the buffer consumed.

    Returns a summary dict; on any failure the summary explains why and no
    exception escapes.
    """
    summary: dict[str, Any] = {"sent": 0, "failed": 0, "dropped": 0, "types": {}, "events": []}

    if not getattr(ctx, "ready", False) or ctx.api is None:
        summary["reason"] = getattr(ctx, "reason", "") or "not ready"
        return summary

    try:
        records = Buffer(ctx).consume()
    except Exception as exc:  # pragma: no cover - state dir unreadable
        summary["reason"] = f"buffer unreadable: {exc}"
        return summary

    for record in records:
        mtype = record.get("mtype")
        messages = _wire_messages(record.get("window") or [])
        if not mtype or not messages:
            summary["dropped"] += 1
            continue

        kwargs: dict[str, Any] = {
            "infer": True,
            "metadata": ctx.provenance(mtype),
            "user_id": ctx.user_id,
        }
        # preference is user-scoped: no app_id, so it follows the developer.
        if mtype not in USER_SCOPED_TYPES:
            kwargs["app_id"] = ctx.app_id

        try:
            status, body = ctx.api.add(messages, **kwargs)
        except Exception as exc:  # pragma: no cover - Api itself never raises
            summary["failed"] += 1
            summary.setdefault("errors", []).append(str(exc)[:200])
            continue

        if 200 <= int(status or 0) < 300:
            summary["sent"] += 1
            summary["types"][mtype] = summary["types"].get(mtype, 0) + 1
            # The response is only {event_id, status: PENDING}; never read it back.
            if isinstance(body, dict) and body.get("event_id"):
                summary["events"].append(body["event_id"])
        else:
            summary["failed"] += 1
            summary.setdefault("errors", []).append({"status": status, "body": body})

    try:
        ctx.log("capture_flush", **{k: v for k, v in summary.items() if k != "errors"})
    except Exception:
        pass
    return summary


# --------------------------------------------------------------------------
# session state
# --------------------------------------------------------------------------
def upsert_session_state(ctx, text: str) -> str:
    """One open-thread record per session: create it once, then update in place.

    CRITICAL: written as a SINGLE user-role message. Verified live that
    infer=False stores assistant-role messages too, contrary to the docs, so a
    two-message payload would produce two records and role filtering cannot be
    relied on to clean it up.
    """
    if not getattr(ctx, "ready", False) or ctx.api is None:
        return "skipped"
    text = (text or "").strip()
    if not text:
        return "skipped"

    existing_id = None
    try:
        status, body = ctx.api.get_all(
            filters.session_state(ctx.user_id, ctx.app_id, ctx.session_id), page_size=5
        )
        if 200 <= int(status or 0) < 300:
            for row in results_of(body):
                if isinstance(row, dict) and row.get("id"):
                    existing_id = row["id"]
                    break
    except Exception:
        existing_id = None

    try:
        if existing_id:
            status, _ = ctx.api.update(existing_id, text=text)
            outcome = "updated" if 200 <= int(status or 0) < 300 else "failed"
        else:
            status, _ = ctx.api.add(
                [{"role": "user", "content": text}],
                infer=False,
                expiration_date=expiry_date(SESSION_STATE_TTL_DAYS),
                metadata=ctx.provenance("session_state"),
                user_id=ctx.user_id,
                app_id=ctx.app_id,
            )
            outcome = "created" if 200 <= int(status or 0) < 300 else "failed"
    except Exception:  # pragma: no cover - Api itself never raises
        outcome = "failed"

    try:
        ctx.log("session_state", outcome=outcome)
    except Exception:
        pass
    return outcome
