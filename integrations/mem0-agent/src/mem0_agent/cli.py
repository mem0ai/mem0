"""mem0-agent command line. Every hook in the editor calls one of these.

Design rules enforced here:
* `observe` performs NO network I/O -- it is on the hot path (every user prompt).
* `context` is the single injection point.
* Writes happen only at session boundaries (`flush`).
* Nothing ever exits non-zero into a hook: memory failing must not break a session.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import capture, ctx as ctx_mod, maintain, pack, transcript
from .api import results_of
from .config import apply_project_config, filters as F
from .config.project_config import TYPES
from .settings import CAPTURE_LEVELS, MEMORY_MODES, RETRIEVAL_LEVELS, Settings


# --------------------------------------------------------------------------
# hook plumbing
# --------------------------------------------------------------------------
def hook_input(timeout: float = 0.25) -> dict:
    """Editors hand hooks a JSON payload on stdin. Absent or malformed is fine.

    Never blocks. A hook's stdin is written and closed, but a manual invocation inherits
    an open pipe with nothing in it -- reading that would hang the command forever.
    """
    stream = sys.stdin
    if stream is None or not hasattr(stream, "read"):
        return {}
    try:
        if stream.isatty():
            return {}
    except Exception:
        return {}

    # StringIO and friends (tests) are readable immediately; real pipes get a poll.
    if hasattr(stream, "fileno"):
        try:
            import select

            if not select.select([stream], [], [], timeout)[0]:
                return {}
        except Exception:
            pass  # not selectable (e.g. StringIO) -- fall through and read
    try:
        raw = stream.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def build(args, payload: dict, *, strict: bool = False):
    session_id = getattr(args, "session_id", None) or payload.get("session_id")
    return ctx_mod.build(session_id, strict=strict)


def emit(text: str) -> None:
    """Anything printed to stdout by a SessionStart hook is added to the model's context."""
    if text:
        sys.stdout.write(text.rstrip() + "\n")


PENDING_FILE = "pending_context.jsonl"


def queue_context(c, block: str) -> None:
    """Park a block for the next prompt hook to deliver.

    The error assist runs detached so its network call stays off the hot path -- which
    also means its stdout goes nowhere. It queues here instead, and `observe` (which
    already runs on every prompt, locally) drains it into context.
    """
    if block:
        c.state.append(PENDING_FILE, {"block": block})


def drain_context(c) -> str:
    rows = c.state.read_lines(PENDING_FILE)
    if not rows:
        return ""
    try:
        (c.state.dir / PENDING_FILE).unlink()
    except Exception:
        try:
            (c.state.dir / PENDING_FILE).write_text("")
        except Exception:
            return ""
    return "\n".join(r.get("block", "") for r in rows if r.get("block"))


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_setup(args) -> int:
    c = build(args, hook_input())
    if not c.ready:
        print(f"not configured: {c.reason}")
        return 0
    report = apply_project_config(c.api)
    print(report.summary())
    return 0


def cmd_onboard(args) -> int:
    from .onboard import run_onboard

    result = run_onboard(interactive=not args.non_interactive, mode=args.mode)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_context(args) -> int:
    """SessionStart: the one injection. Silent when there is nothing worth saying."""
    payload = hook_input()
    c = build(args, payload)
    if not c.ready:
        return 0
    notice = c.api.breaker.take_notice() if c.api else None
    if notice:
        emit(f"<!-- mem0: {notice} -->")
        return 0
    p = pack.build_pack(c, session_id=c.session_id, force=args.force)
    if p.text:
        pack.record_served(c, p.ids)
        emit(p.text)
    c.log("context", rows=p.rows, tokens=p.tokens, ms=p.latency_ms, cached=p.cached)
    if args.stats:
        print(f"\n<!-- rows={p.rows} tokens={p.tokens} {p.latency_ms}ms cached={p.cached} -->",
              file=sys.stderr)
    return 0


def cmd_observe(args) -> int:
    """UserPromptSubmit: local rules only. No network call may happen here."""
    payload = hook_input()
    c = build(args, payload)
    if not c.ready:
        return 0

    # Deliver anything the detached error assist queued since the last prompt.
    emit(drain_context(c))

    tpath = args.transcript or payload.get("transcript_path")
    turns = transcript.read_turns(tpath) if tpath else []
    prompt = payload.get("prompt") or ""
    if prompt:
        turns = turns + [{"role": "user", "content": prompt, "tool_only": False}]
    if not turns:
        return 0

    cursor = c.state.read("cursor.json", {}) or {}
    processed = int(cursor.get("turns", 0))
    level = c.settings.get("capture", "balanced")
    seen = 0
    for window in transcript.windows_since(turns, processed):
        capture.observe(c, window, level)
        seen += len(window)
    c.state.write("cursor.json", {"turns": processed + seen})

    # A served memory being referenced back is our only real relevance signal.
    if prompt:
        pack.note_reference(c, prompt)
    return 0


def cmd_flush(args) -> int:
    """Stop / PreCompact / SessionEnd: the only place writes happen."""
    payload = hook_input()
    c = build(args, payload)
    if not c.ready:
        return 0

    tpath = args.transcript or payload.get("transcript_path")
    turns = transcript.read_turns(tpath) if tpath else []
    if turns:
        cursor = c.state.read("cursor.json", {}) or {}
        processed = int(cursor.get("turns", 0))
        level = c.settings.get("capture", "balanced")
        for window in transcript.windows_since(turns, processed):
            capture.observe(c, window, level)
        c.state.write("cursor.json", {"turns": len(turns)})

    summary = capture.flush(c)

    thread = transcript.summarize_open_thread(turns)
    if thread:
        summary["session_state"] = capture.upsert_session_state(c, thread)

    c.log("flush", reason=args.reason, **{k: v for k, v in summary.items() if k != "events"})
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    return 0


def cmd_assist_error(args) -> int:
    """PostToolUse on Bash: a targeted lookup, or silence."""
    payload = hook_input()
    c = build(args, payload)
    if not c.ready:
        return 0
    text = args.text or ""
    if not text:
        resp = payload.get("tool_response")
        if isinstance(resp, dict):
            text = " ".join(str(resp.get(k, "")) for k in ("stdout", "stderr", "output"))
        elif isinstance(resp, str):
            text = resp
    from .assist import assist

    block = assist(c, text)
    if block:
        if args.emit:
            emit(block)          # synchronous invocation (tests, manual use)
        else:
            queue_context(c, block)  # detached hook: the next prompt delivers it
        c.log("assist", served=True)
    return 0


def cmd_remember(args) -> int:
    c = build(args, hook_input())
    if not c.ready:
        print(f"not configured: {c.reason}")
        return 0
    mtype = args.type if args.type in TYPES else "preference"
    result = capture.remember(c, args.text, mtype) if hasattr(capture, "remember") else None
    if result is None:
        from .config.project_config import USER_SCOPED_TYPES

        kw: dict[str, Any] = {"user_id": c.user_id, "infer": False,
                              "metadata": c.provenance(mtype)}
        if mtype not in USER_SCOPED_TYPES:
            kw["app_id"] = c.app_id
        status, _ = c.api.add([{"role": "user", "content": args.text}], **kw)
        result = {"stored": status == 200, "type": mtype}
    print(f"remembered [{mtype}]: {args.text}" if result.get("stored")
          else f"could not store: {result}")
    return 0


def cmd_forget(args) -> int:
    c = build(args, hook_input())
    if not c.ready:
        print(f"not configured: {c.reason}")
        return 0
    if args.id:
        if not args.confirm:
            print("refusing to delete without --confirm")
            return 0
        c.api.feedback(args.id, "NEGATIVE", "user asked to forget")
        status, _ = c.api.delete(args.id)
        print("deleted" if status == 200 else "delete failed")
        return 0
    status, body = c.api.search(args.query, F.all_in_scope(c.user_id, c.app_id), top_k=8)
    rows = results_of(body)
    if not rows:
        print("no matching memories")
        return 0
    for i, row in enumerate(rows, 1):
        mtype = (row.get("metadata") or {}).get("type") or "?"
        print(f"{i}. [{mtype}] {row.get('memory','')}\n   id={row.get('id')}")
    print("\nRe-run with --id <id> --confirm to delete.")
    return 0


def cmd_maintain(args) -> int:
    c = build(args, hook_input())
    if not c.ready:
        print(f"not configured: {c.reason}")
        return 0
    out = maintain.run(c, dry_run=not args.apply)
    print(out["plan"])
    for m in out.get("merges", [])[:10]:
        print(f"  merge {m['count']} -> {m['keep_text'][:70]}")
    for e in out.get("expiries", [])[:10]:
        print(f"  expire {e['text'][:70]}")
    if not args.apply:
        print("\ndry run; re-run with --apply to execute")
    else:
        print(f"merged={out['merged']} deleted={out['deleted']} expired={out['expired']}")
    return 0


def cmd_health(args) -> int:
    c = build(args, hook_input())
    checks: list[tuple[str, bool, str]] = []
    checks.append(("credentials", c.api is not None, c.reason or "key found"))
    if c.api:
        status, body = c.api.ping()
        ok = status == 200
        checks.append(("connectivity", ok, f"HTTP {status}"))
        if ok and isinstance(body, dict):
            checks.append(("identity", True, f"{c.user_id} @ {body.get('user_email','?')}"))
        checks.append(("scope", bool(c.app_id), f"app_id={c.app_id} branch={c.branch}"))
        checks.append(("breaker", c.api.breaker.allow(), "closed" if c.api.breaker.allow() else "OPEN"))
        st, cfg = c.api.project_get(fields=["custom_categories", "decay"])
        cats = [next(iter(x)) for x in (cfg or {}).get("custom_categories") or []
                if isinstance(x, dict)]
        checks.append(("project config", set(cats) == set(TYPES) and (cfg or {}).get("decay") is True,
                       f"categories={len(cats)} decay={(cfg or {}).get('decay')}"))
        st2, body2 = c.api.get_all(F.all_in_scope(c.user_id, c.app_id), page_size=1)
        total = (body2 or {}).get("count") if isinstance(body2, dict) else None
        checks.append(("read path", st2 == 200, f"corpus={total if total is not None else '?'}"))
    width = max(len(n) for n, _, _ in checks)
    for name, ok, detail in checks:
        print(f"  [{'ok ' if ok else 'FAIL'}] {name.ljust(width)}  {detail}")
    return 0


def cmd_stats(args) -> int:
    c = build(args, hook_input())
    if not c.ready:
        print(f"not configured: {c.reason}")
        return 0
    events = c.state.read_lines("events.jsonl")
    obs = [e for e in events if e.get("event") == "observe"]
    actions: dict[str, int] = {}
    for e in obs:
        actions[e.get("action", "?")] = actions.get(e.get("action", "?"), 0) + 1
    print(f"session {c.session_id}")
    print(f"  turns classified: {len(obs)}  " +
          "  ".join(f"{k}={v}" for k, v in sorted(actions.items())))
    for e in events:
        if e.get("event") == "flush":
            print(f"  flush: sent={e.get('sent')} failed={e.get('failed')} "
                  f"session_state={e.get('session_state','-')}")
        if e.get("event") == "context":
            print(f"  pack: rows={e.get('rows')} tokens={e.get('tokens')} {e.get('ms')}ms")
    if not args.session:
        counts: dict[str, int] = {}
        status, body = c.api.get_all(F.all_in_scope(c.user_id, c.app_id), page_size=100)
        for row in results_of(body):
            t = (row.get("metadata") or {}).get("type") or (
                (row.get("categories") or ["untyped"])[0])
            counts[t] = counts.get(t, 0) + 1
        print(f"\ncorpus for {c.user_id} @ {c.app_id}")
        for t, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {t:14s} {n}")
    return 0


def cmd_config(args) -> int:
    s = Settings.load()
    changed = []
    if args.capture:
        s.set("capture", args.capture)
        changed.append("capture")
    if args.retrieval:
        s.set("retrieval", args.retrieval)
        changed.append("retrieval")
    if args.mode:
        c = build(args, {})
        if c.app_id:
            s.set_project_setting(c.app_id, "memory_mode", args.mode)
        else:
            s.set("memory_mode", args.mode)
        changed.append("memory_mode")
    print(f"capture   = {s.get('capture')}")
    print(f"retrieval = {s.get('retrieval')}  (budget {s.retrieval_budget} tokens)")
    print(f"mode      = {s.get('memory_mode')}")
    if changed:
        print(f"updated: {', '.join(changed)}")
    return 0


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mem0-agent", description="Coding-agent memory")
    p.add_argument("--session-id")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("setup", help="apply project configuration")
    sp.set_defaults(fn=cmd_setup)

    sp = sub.add_parser("onboard", help="first-run setup")
    sp.add_argument("--non-interactive", action="store_true")
    sp.add_argument("--mode", choices=MEMORY_MODES)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_onboard)

    sp = sub.add_parser("context", help="emit the session context pack")
    sp.add_argument("--force", action="store_true", help="bypass the local cache")
    sp.add_argument("--stats", action="store_true")
    sp.set_defaults(fn=cmd_context)

    sp = sub.add_parser("observe", help="classify recent turns (local only)")
    sp.add_argument("--transcript")
    sp.add_argument("--source", default="prompt")
    sp.set_defaults(fn=cmd_observe)

    sp = sub.add_parser("flush", help="write buffered candidates")
    sp.add_argument("--transcript")
    sp.add_argument("--reason", default="stop")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_flush)

    sp = sub.add_parser("assist-error", help="look up a past fix for an error")
    sp.add_argument("--text")
    sp.add_argument("--emit", action="store_true",
                    help="print the block instead of queueing it for the next prompt")
    sp.set_defaults(fn=cmd_assist_error)

    sp = sub.add_parser("remember", help="store a fact verbatim")
    sp.add_argument("--text", required=True)
    sp.add_argument("--type", default="preference", choices=list(TYPES))
    sp.set_defaults(fn=cmd_remember)

    sp = sub.add_parser("forget", help="find and delete memories")
    sp.add_argument("--query")
    sp.add_argument("--id")
    sp.add_argument("--confirm", action="store_true")
    sp.set_defaults(fn=cmd_forget)

    sp = sub.add_parser("maintain", help="consolidate near-duplicates, retire stale insights")
    sp.add_argument("--apply", action="store_true")
    sp.set_defaults(fn=cmd_maintain)

    sp = sub.add_parser("health", help="diagnose the memory layer")
    sp.set_defaults(fn=cmd_health)

    sp = sub.add_parser("stats", help="what was captured and served")
    sp.add_argument("--session", action="store_true")
    sp.set_defaults(fn=cmd_stats)

    sp = sub.add_parser("config", help="capture/retrieval dials and memory mode")
    sp.add_argument("--capture", choices=list(CAPTURE_LEVELS))
    sp.add_argument("--retrieval", choices=list(RETRIEVAL_LEVELS))
    sp.add_argument("--mode", choices=list(MEMORY_MODES))
    sp.set_defaults(fn=cmd_config)

    args = p.parse_args(argv)
    try:
        return args.fn(args) or 0
    except Exception as e:  # a hook must never break the session
        print(f"mem0-agent: {type(e).__name__}: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
