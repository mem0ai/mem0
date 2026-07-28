"""Consolidation must never lose data, and must never touch a pinned memory."""


from mem0_agent import maintain
from mem0_agent.maintain import jaccard, tokens


class FakeApi:
    def __init__(self, rows, fail_add=False, fail_delete=False):
        self.rows = rows
        self.added, self.deleted, self.updated = [], [], []
        self.fail_add = fail_add
        self.fail_delete = fail_delete

    def get_all(self, filters, page=1, page_size=50, **kw):
        return (200, {"results": self.rows if page == 1 else []})

    def add(self, messages, **kw):
        if self.fail_add:
            return (500, {"error": "boom"})
        self.added.append((messages, kw))
        return (200, {"event_id": "e1", "status": "PENDING"})

    def delete(self, mid, **kw):
        if self.fail_delete:
            return (500, {"error": "boom"})
        self.deleted.append(mid)
        return (200, {"message": "ok"})

    def update(self, mid, **kw):
        self.updated.append((mid, kw))
        return (200, {"message": "ok"})


class FakeCtx:
    def __init__(self, api):
        self.api = api
        self.ready = True
        self.user_id, self.app_id, self.session_id = "u", "app", "s"

    def provenance(self, mtype):
        return {"type": mtype, "session_id": self.session_id}

    def log(self, *a, **k):
        pass


def mem(mid, text, mtype="insight", pinned=False, created="2026-07-01T00:00:00"):
    md = {"type": mtype}
    if pinned:
        md["pinned"] = True
    return {"id": mid, "memory": text, "metadata": md, "created_at": created,
            "updated_at": created, "categories": [mtype]}


HEARTBEATS = [
    mem("h1", "Training reached epoch 0.73 of 2 with loss 0.47 and ETA 124 minutes"),
    mem("h2", "Training reached epoch 0.72 of 2 with loss 0.43 and ETA 166 minutes"),
    mem("h3", "Training reached epoch 0.71 of 2 with loss 0.44 and ETA 169 minutes"),
]


def test_jaccard_flags_the_real_heartbeat_cluster():
    a, b = tokens(HEARTBEATS[0]["memory"]), tokens(HEARTBEATS[1]["memory"])
    assert jaccard(a, b) >= maintain.NEAR_DUP_THRESHOLD


def test_plan_clusters_near_duplicates_transitively():
    ctx = FakeCtx(FakeApi(HEARTBEATS))
    p = maintain.plan(ctx)
    assert len(p.merges) == 1
    assert p.merges[0]["count"] == 3
    assert set(p.merges[0]["sources"]) == {"h1", "h2", "h3"}


def test_distinct_memories_are_not_merged():
    rows = [
        mem("a", "pytest in server/ needs docker compose up first"),
        mem("b", "the release tag prefix for the node CLI is cli-node-v"),
    ]
    p = maintain.plan(FakeCtx(FakeApi(rows)))
    assert p.merges == []


def test_different_types_never_merge_even_when_similar():
    rows = [
        mem("a", "always run the type checker before committing", "preference"),
        mem("b", "always run the type checker before committing", "convention"),
    ]
    p = maintain.plan(FakeCtx(FakeApi(rows)))
    assert p.merges == []


def test_pinned_memories_are_never_planned():
    rows = HEARTBEATS + [mem("p1", HEARTBEATS[0]["memory"], pinned=True)]
    p = maintain.plan(FakeCtx(FakeApi(rows)))
    assert all("p1" not in m["sources"] for m in p.merges)
    assert p.scanned == 3


def test_dry_run_changes_nothing():
    api = FakeApi(HEARTBEATS)
    out = maintain.run(FakeCtx(api), dry_run=True)
    assert out["dry_run"] is True
    assert api.added == [] and api.deleted == []


def test_apply_adds_before_deleting():
    api = FakeApi(list(HEARTBEATS))
    ctx = FakeCtx(api)
    out = maintain.run(ctx, dry_run=False)
    assert out["merged"] == 1
    assert out["deleted"] == 3
    # the merged record is written with infer=False so it is stored verbatim
    assert api.added[0][1]["infer"] is False


def test_failed_merge_leaves_sources_intact():
    """A crash mid-merge must leave a duplicate, never a hole."""
    api = FakeApi(list(HEARTBEATS), fail_add=True)
    out = maintain.run(FakeCtx(api), dry_run=False)
    assert out["merged"] == 0
    assert api.deleted == [], "sources must survive when the merged write fails"
    assert out["skipped"] == 1


def test_stale_insights_are_expired_not_deleted():
    old = mem("old", "a gotcha nobody has needed in a year", created="2025-01-01T00:00:00")
    api = FakeApi([old])
    out = maintain.run(FakeCtx(api), dry_run=False, stale_days=180)
    assert out["expired"] == 1
    assert api.deleted == [], "expiration hides; it must not delete"
    assert "expiration_date" in api.updated[0][1]


def test_recent_insights_are_left_alone():
    import time
    recent = mem("new", "a gotcha found this week",
                 created=time.strftime("%Y-%m-%dT%H:%M:%S"))
    p = maintain.plan(FakeCtx(FakeApi([recent])))
    assert p.expiries == []


def test_unready_context_is_a_noop():
    ctx = FakeCtx(FakeApi([]))
    ctx.ready = False
    p = maintain.plan(ctx)
    assert p.scanned == 0 and p.errors
