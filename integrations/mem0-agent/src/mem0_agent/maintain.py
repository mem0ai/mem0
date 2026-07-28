"""Weekly consolidation: merge near-duplicates, retire stale insights.

v1's equivalent was a manual skill whose merge was delete-delete-then-add, so a failure
halfway through lost both originals. This one adds the merged memory FIRST, verifies it,
and only then deletes the sources -- a crash leaves a duplicate, never a hole.

Nothing here deletes without a dry run being available, and pinned memories are untouchable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable

from .api import expiry_date, results_of
from .config import filters as F
from .config.project_config import POLICY_VERSION

NEAR_DUP_THRESHOLD = 0.6
STALE_INSIGHT_DAYS = 180
STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "user", "assistant", "when",
    "into", "than", "then", "they", "their", "there", "have", "has", "was", "were",
    "will", "would", "should", "must", "not", "but", "are", "its", "it's",
}


def tokens(text: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split()
            if len(w) > 2 and w not in STOPWORDS}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_pinned(mem: dict) -> bool:
    return bool((mem.get("metadata") or {}).get("pinned"))


def mem_type(mem: dict) -> str:
    md = mem.get("metadata") or {}
    if md.get("type"):
        return md["type"]
    cats = mem.get("categories") or []
    return cats[0] if cats else "unknown"


@dataclass
class Plan:
    """What maintenance intends to do. Printable before anything is executed."""

    merges: list[dict] = field(default_factory=list)
    expiries: list[dict] = field(default_factory=list)
    scanned: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"scanned={self.scanned} merges={len(self.merges)} "
                f"expiries={len(self.expiries)} errors={len(self.errors)}")


def _cluster(mems: list[dict], threshold: float) -> list[list[dict]]:
    """Union-find over near-duplicate pairs, so a chain of similar memories merges once."""
    toks = [tokens(m.get("memory", "")) for m in mems]
    parent = list(range(len(mems)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in combinations(range(len(mems)), 2):
        if mem_type(mems[i]) != mem_type(mems[j]):
            continue
        if jaccard(toks[i], toks[j]) >= threshold:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj

    groups: dict[int, list[dict]] = {}
    for idx in range(len(mems)):
        groups.setdefault(find(idx), []).append(mems[idx])
    return [g for g in groups.values() if len(g) > 1]


def _newest(group: Iterable[dict]) -> dict:
    return sorted(group, key=lambda m: m.get("created_at") or "", reverse=True)[0]


def fetch_scope(ctx, page_size: int = 100, max_pages: int = 20) -> list[dict]:
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        status, body = ctx.api.get_all(F.all_in_scope(ctx.user_id, ctx.app_id),
                                       page=page, page_size=page_size)
        if status != 200:
            break
        rows = results_of(body)
        out.extend(rows)
        if len(rows) < page_size:
            break
    return out


def plan(ctx, *, threshold: float = NEAR_DUP_THRESHOLD,
         stale_days: int = STALE_INSIGHT_DAYS, now: float | None = None) -> Plan:
    """Read-only. Decides what should change without changing anything."""
    p = Plan()
    if not ctx.ready:
        p.errors.append("context not ready")
        return p
    mems = [m for m in fetch_scope(ctx) if not is_pinned(m)]
    p.scanned = len(mems)

    for group in _cluster(mems, threshold):
        keep = _newest(group)
        p.merges.append({
            "keep_text": keep.get("memory", ""),
            "type": mem_type(keep),
            "sources": [m["id"] for m in group],
            "count": len(group),
        })

    # Stale insights that decay has never reinforced: hide them rather than delete.
    import time as _t
    cutoff = (_t.time() if now is None else now) - stale_days * 86400
    for m in mems:
        if mem_type(m) != "insight" or m.get("expiration_date"):
            continue
        ts = m.get("updated_at") or m.get("created_at") or ""
        try:
            when = _t.mktime(_t.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            continue
        if when < cutoff:
            p.expiries.append({"id": m["id"], "text": (m.get("memory") or "")[:80]})
    return p


def apply(ctx, p: Plan, *, dry_run: bool = True) -> dict:
    """Execute a plan. Merge order is add -> verify -> delete, never the reverse."""
    done = {"merged": 0, "deleted": 0, "expired": 0, "skipped": 0, "errors": []}
    if dry_run:
        done["dry_run"] = True
        return done

    for merge in p.merges:
        meta = ctx.provenance(merge["type"])
        meta["source"] = "maintain"
        meta["policy"] = POLICY_VERSION
        status, _ = ctx.api.add(
            [{"role": "user", "content": merge["keep_text"]}],
            user_id=ctx.user_id, app_id=ctx.app_id, infer=False, metadata=meta,
        )
        if status != 200:
            done["errors"].append(f"merge add failed: {merge['sources'][:1]}")
            done["skipped"] += 1
            continue  # sources survive; a retry can merge them again
        done["merged"] += 1
        for mid in merge["sources"]:
            dstatus, _ = ctx.api.delete(mid)
            if dstatus == 200:
                done["deleted"] += 1
            else:
                done["errors"].append(f"delete failed: {mid}")

    for exp in p.expiries:
        status, _ = ctx.api.update(exp["id"], expiration_date=expiry_date(0))
        if status == 200:
            done["expired"] += 1
        else:
            done["errors"].append(f"expire failed: {exp['id']}")
    return done


def run(ctx, *, dry_run: bool = True, **kw) -> dict:
    p = plan(ctx, **kw)
    result = apply(ctx, p, dry_run=dry_run)
    result["plan"] = p.summary()
    result["merges"] = p.merges
    result["expiries"] = p.expiries
    return result
