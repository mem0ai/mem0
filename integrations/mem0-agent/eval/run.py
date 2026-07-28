#!/usr/bin/env python3
"""Write-gate evaluation harness.

v1 shipped with no way to measure extraction quality, so it degraded unnoticed for
three months: 20.5% of the corpus turned into near-duplicate heartbeats and organic
searches fell from 257/month to 75/month. Nobody noticed because nobody could look.
This harness is the thing that looks.

Two modes:

  --offline (default, no network)
      Runs every fixture through mem0_agent.triggers.classify and scores the client's
      local rules: hard-drop recall, hard-drop precision, flag precision/recall and
      per-type accuracy. Costs nothing, so it can run in CI on every commit.

  --live --project-id P --org-id O
      Replays the `exclude` and `extract` fixtures against a SCRATCH project through
      mem0_agent.api.Api with infer=True, polls until extraction lands, reads back and
      scores what the platform actually stored. This measures the half of the gate that
      lives in the custom instructions and cannot be unit-tested.

Both modes print a scorecard and write eval/last_report.json. `--check` turns the run
into a gate: it exits non-zero if hard-drop recall drops below 0.95 or extract recall
below 0.80, so no edit to the trigger rules or the custom instructions ships unmeasured.

Classifier contract (offline mode)
----------------------------------
`mem0_agent.triggers.classify(window)` is expected to take the message-window list and
return a decision. The adapter below accepts every reasonable shape -- a bool, a string,
a (decision, type) pair, a dict, or an object with attributes -- because the module is
built in parallel with this one. If the module is missing, offline scoring is skipped
with a clear message rather than crashing; if it exists but returns something
unreadable, that is reported as a contract mismatch, not as a score.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, str(EVAL_DIR.parent / "src"))

import fixtures as fx  # noqa: E402

REPORT_PATH = EVAL_DIR / "last_report.json"

# --check gates. Raise them only when the measured score has been above the new bar for
# a while; lowering one is a decision that belongs in a PR description.
THRESHOLDS: dict[str, float] = {
    "hard_drop_recall": 0.95,
    "extract_recall": 0.80,
}

# Text that must never appear inside a stored memory. If one of these survives the gate
# the heartbeat class is leaking again, which is precisely how v1 rotted.
NOISE_PATTERNS = [
    re.compile(r"\beta\b[^.]{0,20}\b\d", re.I),
    re.compile(r"\bepoch\b", re.I),
    re.compile(r"\d+\s*%\s*(complete|done)", re.I),
    re.compile(r"chunks?\s+processed", re.I),
    re.compile(r"\bpid\s*\d+", re.I),
    re.compile(r"\bgradient\s+norm\b", re.I),
    re.compile(r"\bqueue\s+depth\b", re.I),
    re.compile(r"\belapsed\s+\d\d:\d\d", re.I),
]


def noise_leaks(text: str) -> list[str]:
    return [p.pattern for p in NOISE_PATTERNS if p.search(text or "")]


# ---------------------------------------------------------------------------
# classifier adapter
# ---------------------------------------------------------------------------
# Three outcomes, not two. "drop" is a hard drop -- mechanical noise the client refuses
# to send at any level. "skip" is "nothing worth storing right now", which is a soft miss:
# harmless on an exclude window, a lost memory on an extract one. Collapsing the two
# would hide exactly the regression this harness exists to catch.
_DROP_WORDS = {"drop", "noise", "ignore", "suppress", "reject", "block", "hard_drop"}
_SKIP_WORDS = {"skip", "none", "no", "defer", "wait", "noop", "no_trigger"}
_SEND_WORDS = {"send", "capture", "flag", "flagged", "store", "keep", "extract", "accept", "allow",
               "pass", "yes"}
DECISIONS = ("drop", "skip", "send", "unknown")


class ContractMismatch(RuntimeError):
    """classify() exists but neither its signature nor its return value is readable."""


def load_classifier() -> tuple[Callable | None, str]:
    """Import lazily. triggers.py is written by a parallel workstream and may not exist."""
    try:
        from mem0_agent import triggers  # type: ignore
    except ImportError as e:
        return None, f"mem0_agent.triggers is not available yet ({e})"
    except Exception as e:  # a broken module is a different problem than a missing one
        return None, f"mem0_agent.triggers failed to import: {type(e).__name__}: {e}"
    fn = getattr(triggers, "classify", None)
    if not callable(fn):
        return None, "mem0_agent.triggers exists but has no callable classify()"
    return fn, ""


def _invoke(fn: Callable, window: list[dict], level: str | None = None) -> Any:
    """Try the plausible call shapes, most likely first."""
    attempts: tuple[Callable[[], Any], ...] = ()
    if level:
        attempts += (lambda: fn(window, level), lambda: fn(window, level=level))
    attempts += (
        lambda: fn(window),
        lambda: fn(messages=window),
        lambda: fn(window=window),
        lambda: fn("\n".join(m.get("content", "") for m in window)),
    )
    last: Exception | None = None
    for call in attempts:
        try:
            return call()
        except TypeError as e:
            last = e
    raise ContractMismatch(f"classify() rejected every call shape: {last}")


def _type_of(value: Any) -> str | None:
    if isinstance(value, str) and value.lower() in _known_types():
        return value.lower()
    return None


def _known_types() -> set[str]:
    try:
        from mem0_agent.config.project_config import TYPES

        return set(TYPES)
    except Exception:
        return set(fx.counts_by_type()) | {"session_state"}


def _look(result: Any, names: tuple[str, ...]) -> Any:
    for n in names:
        if isinstance(result, dict):
            if n in result:
                return result[n]
        elif hasattr(result, n):
            return getattr(result, n)
    return None


def normalize(result: Any) -> tuple[str, str | None]:
    """Map whatever classify() returned onto (decision, type|None). See DECISIONS."""
    if result is None:
        return "skip", None
    if isinstance(result, bool):
        return ("send" if result else "skip"), None
    if isinstance(result, str):
        low = result.strip().lower()
        if low in _known_types():
            return "send", low
        if low in _DROP_WORDS:
            return "drop", None
        if low in _SKIP_WORDS:
            return "skip", None
        if low in _SEND_WORDS:
            return "send", None
        return "unknown", None
    if isinstance(result, (tuple, list)):
        if not result:
            return "unknown", None
        decision, _ = normalize(result[0])
        mtype = _type_of(result[1]) if len(result) > 1 else None
        if decision == "unknown" and mtype:
            decision = "send"
        return decision, mtype

    mtype = _type_of(_look(result, ("type", "mtype", "memory_type", "kind")))
    # A string verdict is the most expressive shape, so it wins over the booleans:
    # `flagged=False` cannot tell a hard drop apart from a soft skip.
    verdict = _look(result, ("action", "decision", "verdict", "outcome", "status", "result"))
    if isinstance(verdict, str):
        decision, vtype = normalize(verdict)
        if decision != "unknown":
            return decision, (mtype or vtype)
    drop = _look(result, ("drop", "dropped", "is_drop", "should_drop"))
    if isinstance(drop, bool) and drop:
        return "drop", mtype
    send = _look(result, ("send", "capture", "should_capture", "flag", "flagged", "should_send", "keep"))
    if isinstance(send, bool):
        return ("send" if send else ("skip" if drop is False else "drop")), mtype
    if isinstance(drop, bool):
        return "send", mtype
    if mtype:
        return "send", mtype
    return "unknown", None


def reason_of(result: Any) -> str:
    """Whatever the classifier called this rule -- the most useful column in the report."""
    raw = _look(result, ("reason", "rule", "why", "trigger", "explanation"))
    return str(raw) if isinstance(raw, (str, int)) else ""


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def score_offline(rows: list[dict]) -> dict[str, Any]:
    """rows: {"id","label","expect_type","decision","got_type"}."""
    drops = [r for r in rows if r["label"] == "drop"]
    extracts = [r for r in rows if r["label"] == "extract"]
    excludes = [r for r in rows if r["label"] == "exclude"]
    dropped = [r for r in rows if r["decision"] == "drop"]
    flagged = [r for r in rows if r["decision"] == "send"]

    per_type: dict[str, dict[str, int]] = {}
    for r in extracts:
        want = r["expect_type"] or "unspecified"
        bucket = per_type.setdefault(want, {"n": 0, "correct": 0, "typed": 0})
        bucket["n"] += 1
        if r["got_type"]:
            bucket["typed"] += 1
            if r["got_type"] == want:
                bucket["correct"] += 1
    typed = sum(b["typed"] for b in per_type.values())
    correct = sum(b["correct"] for b in per_type.values())

    return {
        # The metric that keeps the corpus clean: mechanical noise must never be sent.
        # capture.py only forwards windows whose action is "flag", so both "drop" and
        # "skip" satisfy the contract -- the label says "never sent", not "matched a
        # rule named drop".
        "hard_drop_recall": _ratio(sum(1 for r in drops if r["decision"] in ("drop", "skip")), len(drops)),
        # Advisory, not gated: how much of that containment comes from an explicit drop
        # rule rather than from no flag rule happening to match. Noise held back only by
        # the absence of a flag rule leaks the day someone adds one.
        "hard_drop_explicit": _ratio(sum(1 for r in drops if r["decision"] == "drop"), len(drops)),
        # Of everything hard-dropped, how much was safe to drop. A hard drop on an
        # `extract` window is the one unrecoverable error -- the memory is gone and
        # nothing logs a miss. Hard-dropping an `exclude` window is not counted against
        # this: those are meant to be discarded, and doing it locally is simply cheaper.
        "hard_drop_precision": _ratio(sum(1 for r in dropped if r["label"] != "extract"), len(dropped)),
        # The metric that keeps the gate useful: durable knowledge must survive locally.
        "extract_recall": _ratio(sum(1 for r in extracts if r["decision"] == "send"), len(extracts)),
        # Of everything forwarded to the platform, how much was worth forwarding.
        "flag_precision": _ratio(sum(1 for r in flagged if r["label"] == "extract"), len(flagged)),
        # Extract windows lost to a soft "skip" rather than a hard drop. Same lost
        # memory, different fix: a missing flag rule, not an over-broad drop rule.
        "extract_skipped": sum(1 for r in extracts if r["decision"] == "skip"),
        "extract_hard_dropped": sum(1 for r in extracts if r["decision"] == "drop"),
        # Exclude windows the client suppressed locally -- free wins, not required, since
        # the platform instructions are the designated owner of that class.
        "exclude_suppressed_early": _ratio(
            sum(1 for r in excludes if r["decision"] in ("drop", "skip")), len(excludes)),
        "type_accuracy": _ratio(correct, typed),
        "type_coverage": _ratio(typed, len(extracts)),
        "per_type": per_type,
        "unreadable": sum(1 for r in rows if r["decision"] == "unknown"),
    }


def run_offline(level: str | None = None) -> dict[str, Any]:
    fn, why = load_classifier()
    if fn is None:
        return {"mode": "offline", "skipped": True, "reason": why, "scores": {}, "rows": [],
                "level": level}

    rows: list[dict] = []
    try:
        for f in fx.FIXTURES:
            try:
                raw = _invoke(fn, f["window"], level)
                decision, got_type = normalize(raw)
                reason, err = reason_of(raw), ""
            except ContractMismatch:
                raise
            except Exception as e:  # a fixture that blows up the classifier is a real finding
                decision, got_type, reason, err = "unknown", None, "", f"{type(e).__name__}: {e}"
            rows.append({
                "id": f["id"], "label": f["label"], "expect_type": f["expect_type"],
                "decision": decision, "got_type": got_type, "reason": reason, "error": err,
            })
    except ContractMismatch as e:
        return {"mode": "offline", "skipped": True, "reason": str(e), "scores": {}, "rows": [],
                "level": level}

    return {"mode": "offline", "skipped": False, "reason": "", "level": level,
            "scores": score_offline(rows), "rows": rows}


# ---------------------------------------------------------------------------
# live mode
# ---------------------------------------------------------------------------
def _memory_type(mem: dict) -> str | None:
    """Read the type from metadata. NEVER from categories: categorization lags ~3.9h
    (median) and is 0% for memories under an hour old, so a fresh read sees nothing."""
    meta = mem.get("metadata") or {}
    return meta.get("type") if isinstance(meta, dict) else None


def score_live(rows: list[dict]) -> dict[str, Any]:
    extracts = [r for r in rows if r["label"] == "extract"]
    excludes = [r for r in rows if r["label"] == "exclude"]
    per_type: dict[str, dict[str, int]] = {}
    for r in extracts:
        want = r["expect_type"] or "unspecified"
        bucket = per_type.setdefault(want, {"n": 0, "stored": 0, "typed_correct": 0})
        bucket["n"] += 1
        if r["stored"] >= 1:
            bucket["stored"] += 1
        if want in (r["got_types"] or []):
            bucket["typed_correct"] += 1
    return {
        "extract_recall": _ratio(sum(1 for r in extracts if r["stored"] >= 1), len(extracts)),
        "exclude_suppression": _ratio(sum(1 for r in excludes if r["stored"] == 0), len(excludes)),
        "type_match": _ratio(sum(b["typed_correct"] for b in per_type.values()),
                             sum(b["n"] for b in per_type.values())),
        "noise_leak_count": sum(len(r["leaks"]) for r in rows),
        "memories_written": sum(r["stored"] for r in rows),
        "per_type": per_type,
    }


def run_live(args: argparse.Namespace) -> dict[str, Any]:
    from mem0_agent.api import Api, results_of  # noqa: PLC0415
    from mem0_agent.config.filters import all_in_scope  # noqa: PLC0415
    from mem0_agent.config.project_config import POLICY_VERSION  # noqa: PLC0415

    key = args.api_key or os.environ.get("MEM0_API_KEY")
    if not key:
        raise SystemExit("live mode needs an API key: --api-key or MEM0_API_KEY")

    runid = args.run_id or uuid.uuid4().hex[:8]
    app_id = f"eval-{runid}"
    api = Api(key, org_id=args.org_id, project_id=args.project_id, strict=True)

    classifier, why = load_classifier()
    if classifier is None:
        print(f"note: {why}; metadata.type will be stamped from expect_type (self-stamped, "
              f"so type_match measures the round trip only)")

    targets = [f for f in fx.FIXTURES if f["label"] in ("exclude", "extract")]
    print(f"live run {runid}: project={args.project_id} app_id={app_id} fixtures={len(targets)}")

    sent: list[dict] = []
    for f in targets:
        uid = f"eval-{runid}-{f['id']}"
        mtype = f["expect_type"]
        stamped_by = "expect_type"
        if classifier is not None:
            try:
                decision, got = normalize(_invoke(classifier, f["window"], args.level))
                if got:
                    mtype, stamped_by = got, "classifier"
            except Exception:
                pass
        meta = {"session_id": f"eval-{runid}", "editor": "eval-harness",
                "policy": POLICY_VERSION, "fixture": f["id"]}
        if mtype:
            meta["type"] = mtype
        t0 = time.time()
        status, body = api.add(f["window"], user_id=uid, app_id=app_id, infer=True, metadata=meta)
        ok = status in (200, 201, 202)
        print(f"  sent {f['id']:34s} {status} {round(time.time() - t0, 2)}s"
              + ("" if ok else f"  <- {body}"))
        sent.append({"id": f["id"], "label": f["label"], "expect_type": f["expect_type"],
                     "user_id": uid, "add_status": status, "stamped_type": mtype,
                     "stamped_by": stamped_by, "accepted": ok})

    def read(user_id: str) -> list[dict]:
        status, body = api.get_all(all_in_scope(user_id, app_id), page_size=100)
        return results_of(body) if status == 200 else []

    # Poll rather than sleep: extraction landed anywhere from 20s to 5min in validation,
    # so any fixed wait is either wrong or wasteful. Only the extract fixtures have a
    # target to poll for; a zero read on an exclude fixture is only meaningful once the
    # settle window has passed, so those are read once at the end.
    started = time.time()
    deadline = started + args.timeout
    pending = {r["id"]: r["user_id"] for r in sent if r["label"] == "extract" and r["accepted"]}
    landed: dict[str, list[dict]] = {}
    interval = 5.0
    print(f"polling for extraction (timeout {args.timeout:.0f}s, settle {args.min_settle:.0f}s)...")
    while pending and time.time() < deadline:
        time.sleep(min(interval, max(1.0, deadline - time.time())))
        interval = min(interval * 1.4, 20.0)
        for fid, uid in list(pending.items()):
            mems = read(uid)
            if mems:
                landed[fid] = mems
                pending.pop(fid, None)
        print(f"  t+{int(time.time() - started)}s  extract landed "
              f"{len(landed)}/{len(landed) + len(pending)}")
    remaining_settle = args.min_settle - (time.time() - started)
    if remaining_settle > 0:
        print(f"  settling {int(remaining_settle)}s before the suppression read...")
        time.sleep(remaining_settle)

    # Final read for everything: extract fixtures may have gained a second memory since
    # they first landed, and the exclude fixtures are read here for the first time.
    found = {r["id"]: read(r["user_id"]) for r in sent}

    rows: list[dict] = []
    for r in sent:
        mems = found.get(r["id"], [])
        texts = [m.get("memory") or "" for m in mems]
        rows.append({**r,
                     "stored": len(mems),
                     "got_types": sorted({t for t in (_memory_type(m) for m in mems) if t}),
                     "memories": [{"id": m.get("id"), "text": t, "type": _memory_type(m),
                                   "categories": m.get("categories")} for m, t in zip(mems, texts)],
                     "leaks": [lk for t in texts for lk in noise_leaks(t)]})

    report = {"mode": "live", "skipped": False, "reason": "", "run_id": runid,
              "project_id": args.project_id, "app_id": app_id,
              "scores": score_live(rows), "rows": rows}

    if args.cleanup:
        deleted = 0
        for r in rows:
            status, _ = api.delete_all(user_id=r["user_id"], app_id=app_id)
            deleted += r["stored"] if status in (200, 202, 204) else 0
        report["cleanup"] = {"deleted_scopes": len(rows), "deleted_memories": deleted}
        print(f"cleanup: removed {deleted} memories across {len(rows)} scopes")
    else:
        report["cleanup"] = {"skipped": True,
                             "hint": f"delete with app_id={app_id} / user_id prefix eval-{runid}-"}
    return report


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def print_scorecard(report: dict[str, Any]) -> None:
    counts = fx.counts()
    print()
    print("=" * 72)
    title = f"  mem0-agent write gate -- {report['mode']} scorecard"
    if report.get("level"):
        title += f" (level={report['level']})"
    print(title)
    print("=" * 72)
    print(f"  coverage: {fx.coverage_line()}")

    if report.get("skipped"):
        print(f"  SKIPPED: {report['reason']}")
        print("=" * 72)
        return

    scores = report["scores"]
    for name, value in scores.items():
        if name == "per_type" or isinstance(value, dict):
            continue
        gate = THRESHOLDS.get(name)
        shown = "n/a" if value is None else f"{value:.3f}" if isinstance(value, float) else str(value)
        mark = ""
        if gate is not None:
            mark = "  FAIL" if (value is None or value < gate) else "  ok"
            shown += f"  (min {gate:.2f}){mark}"
        print(f"  {name:24s} {shown}")

    per_type = scores.get("per_type") or {}
    if per_type:
        print("  per expected type:")
        for t, b in sorted(per_type.items()):
            body = " ".join(f"{k}={v}" for k, v in b.items())
            print(f"    {t:14s} {body}")

    if report["mode"] == "offline":
        soft = [r for r in report["rows"] if r["label"] == "drop" and r["decision"] == "skip"]
        if soft:
            print(f"  noise contained only by the absence of a flag rule ({len(soft)}, advisory):")
            for r in soft:
                print(f"    {r['id']:38s} {r.get('reason', '')}")
        bad = [r for r in report["rows"]
               if (r["label"] == "drop" and r["decision"] not in ("drop", "skip"))
               or (r["label"] == "extract" and r["decision"] != "send")
               or r["decision"] == "unknown"]
        if bad:
            print(f"  misclassified ({len(bad)}):")
            for r in bad:
                want = "drop" if r["label"] == "drop" else "send"
                detail = r.get("error") or r.get("reason") or ""
                print(f"    {r['id']:38s} want={want:5s} got={r['decision']:8s} {detail}")
    else:
        for r in report["rows"]:
            want = "0" if r["label"] == "exclude" else ">=1"
            ok = (r["stored"] == 0) if r["label"] == "exclude" else (r["stored"] >= 1)
            print(f"  [{'PASS' if ok else 'FAIL'}] {r['id']:34s} stored={r['stored']} want={want} "
                  f"types={r['got_types']}")
            for m in r["memories"]:
                print(f"           -> {(m['text'] or '')[:96]}")
        if scores.get("noise_leak_count"):
            print(f"  NOISE LEAK: {scores['noise_leak_count']} stored memories match heartbeat patterns")
    print(f"  labels: {counts}")
    print("=" * 72)


def check(report: dict[str, Any]) -> tuple[bool, list[str]]:
    """A gate that cannot measure must not pass."""
    if report.get("skipped"):
        return False, [f"nothing was measured: {report['reason']}"]
    failures = []
    scores = report["scores"]
    applicable = {k: v for k, v in THRESHOLDS.items() if k in scores}
    if not applicable:
        return False, [f"no gated metric present in {report['mode']} scores"]
    for name, floor in applicable.items():
        value = scores.get(name)
        if value is None:
            failures.append(f"{name} not measured (threshold {floor})")
        elif value < floor:
            failures.append(f"{name}={value:.3f} below threshold {floor}")
    return (not failures), failures


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="mem0-agent write-gate evaluation")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="score the local trigger rules (default)")
    mode.add_argument("--live", action="store_true", help="replay fixtures against a scratch project")
    p.add_argument("--project-id", help="SCRATCH project id (required for --live)")
    p.add_argument("--org-id", help="org id (required for --live)")
    p.add_argument("--api-key", help="defaults to $MEM0_API_KEY")
    p.add_argument("--run-id", help="override the generated run id")
    p.add_argument("--timeout", type=float, default=360.0, help="live: max seconds to poll (default 360)")
    p.add_argument("--min-settle", type=float, default=60.0,
                   help="live: minimum seconds before a zero read counts as suppression (default 60)")
    p.add_argument("--level", help="capture aggressiveness passed to classify() "
                                   "(conservative|balanced|aggressive); default is the module's own")
    p.add_argument("--cleanup", action="store_true", help="live: delete everything this run wrote")
    p.add_argument("--check", action="store_true", help="exit non-zero if scores regress below thresholds")
    p.add_argument("--report", default=str(REPORT_PATH), help=f"report path (default {REPORT_PATH})")
    args = p.parse_args(argv)

    if args.live:
        # A live run writes real memories. It must never be able to land in production
        # by omission, so both ids are required and neither has a default.
        missing = [n for n, v in (("--project-id", args.project_id), ("--org-id", args.org_id)) if not v]
        if missing:
            p.error("live mode requires " + " and ".join(missing)
                    + " -- point them at a scratch project, never a production one")
        report = run_live(args)
    else:
        report = run_offline(args.level)

    report["thresholds"] = THRESHOLDS
    report["fixture_counts"] = fx.counts()
    report["fixture_counts_by_type"] = fx.counts_by_type()
    report["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    passed, failures = check(report)
    report["check"] = {"passed": passed, "failures": failures}

    print_scorecard(report)
    Path(args.report).write_text(json.dumps(report, indent=1))
    print(f"report written to {args.report}")

    if args.check:
        if failures:
            print("CHECK FAILED:")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
