"""Error assist: the only semantic search left on the hot path, and it is opt-in.

v1 fed RAW STDOUT JSON straight into the search query and got zero results back --
an embedding of a 4KB blob of ANSI codes, paths and timestamps matches nothing. Here
the output is first reduced to a *signature*: exception class plus a normalized
message, with paths, line numbers, addresses, uuids and timestamps stripped so the
query generalizes across machines and runs.

Two more rules, both learned from v1:
* Silence beats noise. Nothing clears the threshold -> nothing is injected.
* At the conservative retrieval level this feature is off entirely.

Never raises; safe to call from a background thread.
"""

from __future__ import annotations

import json
import re

from .api import results_of
from .config import filters
from .pack import ASSIST_TAG, NOTE, line_for, record_served, render_frame

MAX_SIG = 120
ASSIST_TOP_K = 3
ASSIST_BUDGET = 400

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_WS = re.compile(r"\s+")

# A real exception line: `pkg.mod.ValueError: message` at the start of a line.
_EXC = re.compile(
    r"^[ \t]*(?:[\w.]+\.)?"
    r"([A-Z]\w*(?:Error|Exception|Fault|Interrupt|Failure|Timeout|Denied|NotFound))"
    r"\b(?:[ \t]*:[ \t]*(.*))?$",
    re.M,
)

# Tool-agnostic error markers: `psql: error: ...`, `ERROR: ...`, `npm ERR! ...`,
# `error TS2345:`, plus the handful of phrases that are always failures.
_MARKER = re.compile(
    r"""(?imx)
    ^[ \t]*(?P<prefix>[^\s:]{0,40}:[ \t]*)?
      (?:error|fatal|failure|panic|err)\b
      [ \t]*(?P<code>[A-Z]{1,4}\d{1,6})?[ \t]*[:!]+[ \t]*(?P<rest>.*)$
    """,
)
_PHRASE = re.compile(
    r"""(?ix)
    \b(?:command\s+not\s+found
       |no\s+such\s+file\s+or\s+directory
       |permission\s+denied
       |connection\s+refused
       |could\s+not\s+connect
       |connection\s+to\s+server
       |segmentation\s+fault
       |cannot\s+find\s+module
       |module\s+not\s+found
       |unhandled\s+(?:exception|rejection))\b
    """,
)

_NORMALIZERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<ts>"),
    (re.compile(r"\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b"), "<ts>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<id>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<addr>"),
    (re.compile(r"[A-Za-z]:\\[^\s'\"]+"), "<path>"),
    (re.compile(r"(?<![\w])(?:~|\.{0,2})?/(?:[\w.+-]+/)+[\w.+-]*"), "<path>"),
    (re.compile(r"(?i)\bline\s+\d+\b"), "line <n>"),
    (re.compile(r":\d+:\d+\b"), ":<n>"),
    (re.compile(r"\b\d{4,}\b"), "<n>"),
    (re.compile(r"\b[0-9a-f]{12,}\b"), "<hash>"),
]


def _normalize(msg: str) -> str:
    s = _ANSI.sub("", msg or "")
    for pat, repl in _NORMALIZERS:
        s = pat.sub(repl, s)
    s = _WS.sub(" ", s).strip().strip("'\"` ")
    return s


def _json_strings(text: str, limit: int = 200) -> str | None:
    """Hook payloads arrive as JSON. Pull the string values out instead of embedding
    the envelope -- searching the literal blob is exactly what v1 did wrong."""
    s = text.strip()
    if not (s.startswith("{") or s.startswith("[")):
        return None
    try:
        obj = json.loads(s)
    except Exception:
        return None
    out: list[str] = []

    def walk(node, depth: int = 0) -> None:
        if len(out) >= limit or depth > 6:
            return
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node:
                walk(v, depth + 1)

    walk(obj)
    return "\n".join(out) or None


def error_signature(text: str | None, _depth: int = 0) -> str | None:
    """A compact, machine-independent signature of a failure, or None.

    Returns at most MAX_SIG chars. Ordinary command output yields None -- that is the
    point: no signature, no search, no injection.
    """
    try:
        if not text or not isinstance(text, str):
            return None
        if _depth == 0:
            unwrapped = _json_strings(text)
            if unwrapped is not None:
                # A JSON envelope is never itself the query; only its contents are.
                return error_signature(unwrapped, _depth + 1)
        clean = _ANSI.sub("", text)
        if len(clean) > 20000:  # only the head and tail of a huge log can matter
            clean = clean[:10000] + "\n" + clean[-10000:]

        # 1. A real exception class is the strongest and most specific signal.
        exc = None
        for m in _EXC.finditer(clean):
            exc = m
        if exc:
            cls = exc.group(1)
            msg = _normalize(exc.group(2) or "")
            sig = f"{cls}: {msg}" if msg else cls
            return sig[:MAX_SIG].strip()

        # 2. A tool-shaped error line: `psql: error: ...`, `ERROR: ...`, `npm ERR! ...`.
        for m in _MARKER.finditer(clean):
            rest = _normalize(m.group("rest") or "")
            if not rest:
                continue
            code = (m.group("code") or "").strip()
            if code:
                rest = f"{code}: {rest}"
            prefix = (m.group("prefix") or "").strip().rstrip(":").strip()
            sig = f"{prefix}: {rest}" if prefix else rest
            return sig[:MAX_SIG].strip()

        # 3. Failure phrases that carry no marker word.
        p = _PHRASE.search(clean)
        if p:
            # A window around the phrase, never the whole line: a 4KB log line must
            # never become the query.
            start = max(clean.rfind("\n", 0, p.start()) + 1, p.start() - 60)
            nl = clean.find("\n", p.end())
            end = min(len(clean) if nl == -1 else nl, p.end() + 60)
            sig = _normalize(clean[start:end])
            return sig[:MAX_SIG].strip() or None
        return None
    except Exception:
        return None


def _score(row: dict) -> float:
    for key in ("score", "relevance", "similarity"):
        val = row.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return 1.0  # scoreless backend: trust the server-side threshold


def assist(ctx, output_text: str | None, *, top_k: int = ASSIST_TOP_K) -> str | None:
    """Signature -> one reranked search -> a small framed block, or None. Never raises."""
    try:
        if ctx is None or not getattr(ctx, "ready", False) or getattr(ctx, "api", None) is None:
            return None
        threshold = getattr(getattr(ctx, "settings", None), "error_assist_threshold", None)
        if threshold is None:  # conservative retrieval level: feature off
            return None
        signature = error_signature(output_text)
        if not signature:
            return None

        try:
            status, body = ctx.api.search(
                signature,
                filters.error_assist(ctx.user_id, ctx.app_id),
                rerank=True,
                top_k=top_k,
                threshold=threshold,
            )
        except Exception:
            return None
        if status != 200:
            return None

        rows = [r for r in results_of(body) if isinstance(r, dict) and _score(r) >= float(threshold)]
        if not rows:
            return None

        lines: list[str] = []
        ids: list[str] = []
        budget = ASSIST_BUDGET
        used = 0
        for row in rows[:top_k]:
            ln = line_for(row)
            if not ln:
                continue
            cost = max(1, len(ln) // 4)
            if used + cost > budget:
                break
            used += cost
            lines.append(ln)
            ids.append(str(row.get("id") or ""))
        if not lines:
            return None

        record_served(ctx, [i for i in ids if i])
        return render_frame(lines, tag=ASSIST_TAG, note=NOTE) or None
    except Exception:
        return None


__all__ = ["assist", "error_signature", "MAX_SIG"]
