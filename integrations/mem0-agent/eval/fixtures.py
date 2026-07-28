"""Labeled windows for the write-gate evaluation.

Every fixture is one turn-window exactly as the client would hand it to the capture
path. The wording of the `drop` and `exclude` entries is taken from the audited v1
corpus -- these are the classes that made 20.5% of that corpus near-duplicate
heartbeats and drove organic searches from 257/month down to 75/month. The `extract`
entries are the knowledge the gate must never throw away.

Labels
------
drop     The client's local trigger rules must hard-drop the window. It never reaches
         the platform, so it costs nothing and can never be stored. Failing to drop
         these is what produced the v1 heartbeat corpus.
exclude  The window may legitimately be sent (a local rule cannot cheaply tell it
         apart from real content), but the platform's custom instructions must store
         NOTHING from it. This is the layer that catches narration, activity logs,
         repo-file contents and one-off directives.
extract  The window must produce at least one memory, ideally of `expect_type`.
         Losing these is the expensive failure: the gate gets quiet and useless.

Schema (every entry, exactly these keys)
----------------------------------------
    id           stable identifier, also the per-fixture user_id suffix in live runs
    window       list of {"role", "content"} messages
    label        "drop" | "exclude" | "extract"
    expect_type  one of mem0_agent.config.project_config.TYPES, or None
    note         why this fixture exists / what regression it guards

Adding a fixture: append it to the right block, give it a fresh id, and say in `note`
which real failure it represents. tests/test_fixtures.py enforces the schema.
"""

from __future__ import annotations

LABELS: tuple[str, ...] = ("drop", "exclude", "extract")


# ---------------------------------------------------------------------------
# DROP -- mechanical noise. The client must never send these.
# ---------------------------------------------------------------------------
_DROP: list[dict] = [
    {
        "id": "d01_train_epoch_eta",
        "window": [
            {"role": "assistant", "content": "Task notification (task-id bukn4vw5n): v4 train metrics at epoch "
                                             "0.7381/2 (37% complete) with loss 0.4727, gradient norm 0.4716, "
                                             "ETA 124 minutes."},
            {"role": "assistant", "content": "Still training. Next update in about 10 minutes."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "The single most duplicated shape in the audited v1 corpus: epoch/loss/ETA training heartbeat.",
    },
    {
        "id": "d02_train_epoch_eta_later",
        "window": [
            {"role": "assistant", "content": "Task notification (task-id bukn4vw5n): v4 train metrics at epoch "
                                             "0.9124/2 (46% complete) with loss 0.4412, gradient norm 0.5031, "
                                             "ETA 101 minutes."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Same shape as d01 twenty minutes later. Repeated same-shape turns are the near-duplicate engine.",
    },
    {
        "id": "d03_train_step_metrics",
        "window": [
            {"role": "assistant", "content": "step 4200/12000 | loss 0.3318 | lr 1.2e-05 | grad_norm 0.61 | "
                                             "throughput 812 tok/s | eta 02:41:15"},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Bare training metric line with no prose at all -- pure telemetry.",
    },
    {
        "id": "d04_chunks_progress",
        "window": [
            {"role": "assistant", "content": "Progress for task bnzbd1uay: 218 of 928 chunks processed "
                                             "(23% complete), approximately 5,141 synthetic memories generated, "
                                             "11 chunk failures, ETA about 55 minutes."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Verbatim v1 corpus wording: the 'N of M chunks processed (X%)' heartbeat.",
    },
    {
        "id": "d05_chunks_progress_mid",
        "window": [
            {"role": "assistant", "content": "Progress for task bnzbd1uay: 466 of 928 chunks processed "
                                             "(50% complete), approximately 10,884 synthetic memories generated, "
                                             "19 chunk failures, ETA about 31 minutes."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Second emission of d04. Differs only in the numbers -- the classic near-duplicate pair.",
    },
    {
        "id": "d06_chunks_progress_late",
        "window": [
            {"role": "assistant", "content": "Progress for task bnzbd1uay: 902 of 928 chunks processed "
                                             "(97% complete), approximately 21,330 synthetic memories generated, "
                                             "24 chunk failures, ETA about 2 minutes."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Third emission. A gate that drops d04 but keeps this one has learned the numbers, not the shape.",
    },
    {
        "id": "d07_markdown_ingest_pid",
        "window": [
            {"role": "assistant", "content": "markdown ingest still running (pid 48213, elapsed 00:14:52); "
                                             "3,204 files indexed so far, 0 errors."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Markdown-ingest heartbeat with pid/elapsed -- second-largest duplicate cluster in the audit.",
    },
    {
        "id": "d08_markdown_ingest_pid_repeat",
        "window": [
            {"role": "assistant", "content": "markdown ingest still running (pid 48213, elapsed 00:29:18); "
                                             "6,771 files indexed so far, 2 errors."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Repeat of d07. Same pid, later elapsed.",
    },
    {
        "id": "d09_ingest_complete_stats",
        "window": [
            {"role": "assistant", "content": "markdown ingest finished (pid 48213, elapsed 00:41:07): "
                                             "9,118 files indexed, 2 errors, 0 skipped."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Terminal heartbeat. Completion counts are still telemetry, not knowledge.",
    },
    {
        "id": "d10_monitor_status_line",
        "window": [
            {"role": "assistant", "content": "monitor: api p50 118ms p99 640ms | queue depth 3 | workers 8/8 "
                                             "healthy | last deploy 41m ago"},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Monitoring status line. True for one instant, useless in any future session.",
    },
    {
        "id": "d11_monitor_all_green",
        "window": [
            {"role": "assistant", "content": "Health check at 09:14:03 - all green. Nothing to do."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Monitoring no-op turn.",
    },
    {
        "id": "d12_tool_only_turn",
        "window": [
            {"role": "assistant", "content": "<tool_use name=\"Bash\">git status --porcelain</tool_use>"},
            {"role": "user", "content": "<tool_result> M src/mem0_agent/api.py\n M tests/test_api.py</tool_result>"},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Tool-only turn: no natural-language content from either party.",
    },
    {
        "id": "d13_tool_only_test_output",
        "window": [
            {"role": "user", "content": "<tool_result>============ 412 passed, 3 skipped in 38.21s "
                                        "============</tool_result>"},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Raw tool output with no interpretation. The lesson, if any, comes in a later turn.",
    },
    {
        "id": "d14_tool_only_ls",
        "window": [
            {"role": "assistant", "content": "<tool_use name=\"Bash\">ls -la integrations/mem0-agent</tool_use>"},
            {"role": "user", "content": "<tool_result>total 0\ndrwxr-xr-x docs\ndrwxr-xr-x eval\ndrwxr-xr-x "
                                        "hooks\ndrwxr-xr-x src\ndrwxr-xr-x tests</tool_result>"},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Directory listing round-trip. Derivable from the repo at any time.",
    },
    {
        "id": "d15_eta_only",
        "window": [
            {"role": "assistant", "content": "Next update in about 10 minutes."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "The shortest heartbeat there is. v1 stored dozens of these.",
    },
    {
        "id": "d16_percent_bar",
        "window": [
            {"role": "assistant", "content": "[####################........] 71% | 1,412/1,988 rows migrated | "
                                             "eta 6m"},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Progress bar render. Mechanical by construction.",
    },
    {
        "id": "d17_still_running_ack",
        "window": [
            {"role": "assistant", "content": "Still running. 41% now."},
            {"role": "user", "content": "ok"},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Heartbeat plus bare acknowledgement. Nothing durable can be extracted from 'ok'.",
    },
    {
        "id": "d18_backfill_job_notification",
        "window": [
            {"role": "assistant", "content": "Task notification (task-id q7z1m4d0c): backfill job 'memories_v3' "
                                             "is 62% complete, 3.1M of 5.0M rows, ETA 22 minutes."},
        ],
        "label": "drop",
        "expect_type": None,
        "note": "Job-notification wrapper, a different job than d01/d04 but the same shape.",
    },
]


# ---------------------------------------------------------------------------
# EXCLUDE -- may be sent; the platform instructions must store nothing.
# ---------------------------------------------------------------------------
_EXCLUDE: list[dict] = [
    {
        "id": "x01_narration_browser_test",
        "window": [
            {"role": "assistant", "content": "Should I drive a browser test (log in, open the agent, send a "
                                             "message), or would you rather click through the UI yourself?"},
            {"role": "user", "content": "you do it"},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "The v1 corpus turned this into 'user prefers the assistant to drive browser tests'. It is a "
                "one-off directive plus assistant narration, not a preference.",
    },
    {
        "id": "x02_narration_plan",
        "window": [
            {"role": "assistant", "content": "I'm going to start by reading api.py and settings.py, then sketch "
                                             "the change, then run the tests before I touch anything else."},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Assistant stating its own plan mid-task. Attribution trap: this is not the user's preference.",
    },
    {
        "id": "x03_narration_asked_whether",
        "window": [
            {"role": "assistant", "content": "I asked whether to keep the old endpoint around during the "
                                             "migration and you said you would think about it."},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Narration of an unresolved exchange. No decision was reached, so nothing durable exists yet.",
    },
    {
        "id": "x04_file_modification_list",
        "window": [
            {"role": "assistant", "content": "I modified VERSION, chat.py, agent.py, types.py, chunking.py, the "
                                             "slack adapter, the router, the tests, and several web components "
                                             "in this session."},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Verbatim v1 wording. Activity that git already records, in higher fidelity, forever.",
    },
    {
        "id": "x05_commit_list",
        "window": [
            {"role": "assistant", "content": "Committed 4 changes: e102b21 foundation, b357a5a release bump, "
                                             "d653b63 milvus guard, cc46715 cassandra filters."},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Commit log restated in prose.",
    },
    {
        "id": "x06_pr_activity",
        "window": [
            {"role": "assistant", "content": "Opened PR #6589 against main and requested review from two "
                                             "teammates; CI is running now."},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "PR bookkeeping, derivable from the forge.",
    },
    {
        "id": "x07_claude_md_excerpt",
        "window": [
            {"role": "user", "content": "## Coding Standards\n\n- Python source files: snake_case.py\n"
                                        "- Test files: test_<module>.py\n- Ruff line length 120\n"
                                        "(this is the contents of our CLAUDE.md)"},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Repo-file contents. This is the one exclude class the platform instructions alone do NOT "
                "suppress -- it reads as genuine convention. The client must drop repo-file pastes locally.",
    },
    {
        "id": "x08_readme_excerpt",
        "window": [
            {"role": "user", "content": "From the README:\n\n## Installation\n\n```bash\npip install mem0ai\n```\n"
                                        "\n## Quickstart\n\n```python\nfrom mem0 import Memory\nm = Memory()\n```"},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "README excerpt. Already in the repo; storing it duplicates a file that will drift.",
    },
    {
        "id": "x09_config_file_excerpt",
        "window": [
            {"role": "user", "content": "Here is our pyproject:\n\n[tool.ruff]\nline-length = 120\n"
                                        "target-version = \"py310\"\n\n[tool.pytest.ini_options]\n"
                                        "testpaths = [\"tests\"]"},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Config file paste. Same class as x07/x08 -- the file is the source of truth, not memory.",
    },
    {
        "id": "x10_one_off_you_do_it",
        "window": [
            {"role": "assistant", "content": "Do you want to run the migration, or should I?"},
            {"role": "user", "content": "you do it"},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "One-off task directive. v1 generalized these into standing preferences.",
    },
    {
        "id": "x11_one_off_skip_tests",
        "window": [
            {"role": "user", "content": "skip tests for now, I just want to see if it compiles"},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Scoped to this moment. Storing it as a preference would suppress tests forever.",
    },
    {
        "id": "x12_one_off_run_yourself",
        "window": [
            {"role": "user", "content": "run it yourself this time, I'm on a call"},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Explicitly a one-time instruction ('this time'), the exact wording the instructions call out.",
    },
    {
        "id": "x13_session_status_time",
        "window": [
            {"role": "assistant", "content": "At 12:45:24 the job was wrapping up; I'll give you a final summary "
                                             "when it completes."},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Verbatim v1 wording. Session-only status with a wall-clock timestamp.",
    },
    {
        "id": "x14_session_only_step",
        "window": [
            {"role": "assistant", "content": "We're on step 3 of 5 of the migration right now; the last two "
                                             "steps are the index rebuild and the cutover."},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Where we are in this session. Session state has its own record and TTL; it is not knowledge.",
    },
    {
        "id": "x15_assistant_self_attribution",
        "window": [
            {"role": "assistant", "content": "I prefer to read the whole file before editing so I don't miss "
                                             "context, so that's what I did here."},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Attribution trap: the assistant's own habit is not the developer's preference.",
    },
    {
        "id": "x16_credentials",
        "window": [
            {"role": "user", "content": "here's the staging key so you can test: "
                                        "MEM0_API_KEY=m0-abc123FAKEnotreal456 and the DSN is "
                                        "postgres://app:hunter2@staging-db:5432/app"},
        ],
        "label": "exclude",
        "expect_type": None,
        "note": "Secrets must never be stored, however useful they look. Explicit exclusion in the instructions.",
    },
]


# ---------------------------------------------------------------------------
# EXTRACT -- durable knowledge. At least one memory, ideally of expect_type.
# ---------------------------------------------------------------------------
_EXTRACT: list[dict] = [
    {
        "id": "e01_pref_test_output_first",
        "window": [
            {"role": "user", "content": "Stop dumping the whole diff at me every time. Show me the failing test "
                                        "output first, then the fix. That's how I want it from now on."},
            {"role": "assistant", "content": "Understood - failing test output first, then the fix."},
        ],
        "label": "extract",
        "expect_type": "preference",
        "note": "Explicit standing preference ('from now on'). Baseline: captured.",
    },
    {
        "id": "e02_pref_no_summary_tables",
        "window": [
            {"role": "user", "content": "In general, don't end your answers with a summary table. Just tell me "
                                        "what changed in two sentences. Applies to every task, not just this one."},
        ],
        "label": "extract",
        "expect_type": "preference",
        "note": "Communication preference, stated as a general rule -- the discriminator against x11/x12.",
    },
    {
        "id": "e03_pref_ask_before_force_push",
        "window": [
            {"role": "user", "content": "Rule for me, always: never force-push a shared branch without asking "
                                        "first. I've been burned by that twice."},
        ],
        "label": "extract",
        "expect_type": "preference",
        "note": "Workflow guardrail with stated motivation.",
    },
    {
        "id": "e04_pref_pnpm_only",
        "window": [
            {"role": "assistant", "content": "Should I use npm install here?"},
            {"role": "user", "content": "No - I always use pnpm for anything TypeScript, in every repo. npm and "
                                        "yarn produce lockfile churn I then have to clean up."},
        ],
        "label": "extract",
        "expect_type": "preference",
        "note": "Tooling preference scoped to the developer, not the repo. Should land at user scope.",
    },
    {
        "id": "e05_decision_pgvector",
        "window": [
            {"role": "user", "content": "Let's go with pgvector instead of Pinecone. I don't want a second "
                                        "vendor to manage, and the latency is fine at our scale."},
            {"role": "assistant", "content": "Going with pgvector then, for vendor consolidation."},
        ],
        "label": "extract",
        "expect_type": "decision",
        "note": "Resolved choice plus reasoning. Baseline: captured (as two memories).",
    },
    {
        "id": "e06_decision_arq_over_celery",
        "window": [
            {"role": "user", "content": "We're dropping Celery and moving the workers to arq. Celery's redis "
                                        "broker config kept drifting between environments and arq is asyncio "
                                        "native, which matches the rest of the service."},
        ],
        "label": "extract",
        "expect_type": "decision",
        "note": "Migration decision with two stated reasons.",
    },
    {
        "id": "e07_decision_metadata_over_categories",
        "window": [
            {"role": "assistant", "content": "We could filter reads on categories or on metadata.type."},
            {"role": "user", "content": "Filter on metadata.type. Categories are assigned by a background job "
                                        "hours later, so a memory written this session would be invisible to a "
                                        "category filter."},
        ],
        "label": "extract",
        "expect_type": "decision",
        "note": "The read-path decision this harness itself depends on.",
    },
    {
        "id": "e08_decision_keep_worktrees",
        "window": [
            {"role": "user", "content": "We'll keep using git worktrees for parallel agent work rather than "
                                        "branch switching - switching branches invalidates the build cache and "
                                        "costs us four minutes every time."},
        ],
        "label": "extract",
        "expect_type": "decision",
        "note": "Process decision with a measured justification.",
    },
    {
        "id": "e09_convention_branch_naming",
        "window": [
            {"role": "assistant", "content": "The push was rejected: this repo's hook requires branch names in "
                                             "the form user/<id>/<name>."},
            {"role": "user", "content": "Right, that's the rule here - always name branches that way."},
        ],
        "label": "extract",
        "expect_type": "convention",
        "note": "Team rule confirmed by the developer, enforced by tooling but not written down.",
    },
    {
        "id": "e10_convention_conventional_commits",
        "window": [
            {"role": "user", "content": "Every commit message in this repo has to be a conventional commit with "
                                        "the package scope, like fix(mem0-agent): .... The release router parses "
                                        "the scope, and it isn't documented anywhere."},
        ],
        "label": "extract",
        "expect_type": "convention",
        "note": "Undocumented team rule with the consequence of breaking it.",
    },
    {
        "id": "e11_convention_no_core_deps",
        "window": [
            {"role": "user", "content": "Never add anything to the core dependencies list - new deps go in an "
                                        "optional group. That's a hard rule on this team; core has to stay "
                                        "installable with no extras."},
        ],
        "label": "extract",
        "expect_type": "convention",
        "note": "Project rule stated as a hard constraint.",
    },
    {
        "id": "e12_insight_pytest_needs_compose",
        "window": [
            {"role": "assistant", "content": "Root cause found: pytest in server/ fails with a misleading "
                                             "postgres connection error unless `docker compose up` is running "
                                             "first. The tests need the compose stack."},
            {"role": "user", "content": "good catch"},
        ],
        "label": "extract",
        "expect_type": "insight",
        "note": "Root-caused gotcha with a misleading symptom. Baseline: captured.",
    },
    {
        "id": "e13_insight_project_id_body",
        "window": [
            {"role": "assistant", "content": "Found it. project_id and org_id have to go in the request body - "
                                             "as query params the API silently ignores them and the write lands "
                                             "in whatever project the API key defaults to. No error, no warning."},
        ],
        "label": "extract",
        "expect_type": "insight",
        "note": "Silent-failure constraint. Exactly the class of thing that costs an hour when forgotten.",
    },
    {
        "id": "e14_insight_not_takes_list",
        "window": [
            {"role": "assistant", "content": "The 400 was the filter shape: NOT takes a list of clauses, not a "
                                             "single object. `{\"NOT\": {...}}` is rejected, `{\"NOT\": [{...}]}` "
                                             "works."},
        ],
        "label": "extract",
        "expect_type": "insight",
        "note": "Non-obvious API shape, generalized past the incident.",
    },
    {
        "id": "e15_insight_latest_only",
        "window": [
            {"role": "user", "content": "So that's why we saw duplicates - reads default to returning superseded "
                                        "memories next to the ones that replaced them. latest_only has to be set "
                                        "on every read or the context pack is full of stale pairs."},
        ],
        "label": "extract",
        "expect_type": "insight",
        "note": "Constraint discovered from a symptom, stated as the general lesson.",
    },
    {
        "id": "e16_runbook_release",
        "window": [
            {"role": "assistant", "content": "Verified the release procedure end to end: bump VERSION, run "
                                             "`make build`, tag with `cli-v<version>`, push the tag, then the "
                                             "release router dispatches the package workflow. Confirmed working "
                                             "on the last release."},
        ],
        "label": "extract",
        "expect_type": "runbook",
        "note": "Multi-step procedure explicitly verified end to end. Baseline: captured.",
    },
    {
        "id": "e17_runbook_local_stack",
        "window": [
            {"role": "assistant", "content": "Local stack bring-up works, confirmed twice: `docker compose up` in "
                                             "server/, wait for neo4j to report healthy on 8474, then "
                                             "`uvicorn main:app --reload` from openmemory/api, then seed with "
                                             "`python scripts/seed.py --demo`. Starting uvicorn before neo4j is "
                                             "healthy fails the first request every time."},
        ],
        "label": "extract",
        "expect_type": "runbook",
        "note": "Ordered procedure with the failure mode of doing it out of order.",
    },
    {
        "id": "e18_runbook_republish",
        "window": [
            {"role": "user", "content": "For a re-publish, don't delete and recreate the GitHub release - "
                                        "dispatch the package workflow by hand instead: "
                                        "`gh workflow run <package>-cd.yml --ref refs/tags/<tag> -f tag=<tag>`. "
                                        "We did that last week and it worked."},
        ],
        "label": "extract",
        "expect_type": "runbook",
        "note": "Verified recovery procedure including the thing not to do.",
    },
    {
        "id": "e19_mixed_insight_bastion",
        "window": [
            {"role": "assistant", "content": "Training at epoch 1.2/3 (40%), ETA 38 minutes."},
            {"role": "user", "content": "while that runs - remember that our staging DB only accepts connections "
                                        "through the bastion host, direct psql always times out."},
            {"role": "assistant", "content": "Noted. Still training, 41% now."},
        ],
        "label": "extract",
        "expect_type": "insight",
        "note": "MIXED: durable fact buried between two heartbeats. The fact must survive, the progress must "
                "not. Baseline: captured, with no heartbeat leakage.",
    },
    {
        "id": "e20_mixed_decision_queue",
        "window": [
            {"role": "assistant", "content": "Progress for task bnzbd1uay: 301 of 928 chunks processed (32% "
                                             "complete), ETA about 44 minutes."},
            {"role": "user", "content": "One thing while we wait: we've decided the ingest queue stays at "
                                        "concurrency 4. Anything higher and the embedding provider starts "
                                        "rate-limiting us, which costs more time than it saves."},
            {"role": "assistant", "content": "Progress for task bnzbd1uay: 318 of 928 chunks processed (34% "
                                             "complete), ETA about 41 minutes."},
        ],
        "label": "extract",
        "expect_type": "decision",
        "note": "MIXED: decision plus reasoning sandwiched between two identical-shape progress lines.",
    },
    {
        "id": "e21_mixed_preference_monitoring",
        "window": [
            {"role": "assistant", "content": "monitor: api p50 121ms p99 655ms | queue depth 2 | workers 8/8 "
                                             "healthy"},
            {"role": "user", "content": "Going forward, when something breaks, show me the smallest repro before "
                                        "you propose a fix. I don't want the fix until I've seen the repro."},
            {"role": "assistant", "content": "monitor: api p50 119ms p99 640ms | queue depth 3 | workers 8/8 "
                                             "healthy"},
        ],
        "label": "extract",
        "expect_type": "preference",
        "note": "MIXED: standing preference between two monitoring lines.",
    },
    {
        "id": "e22_mixed_convention_ingest",
        "window": [
            {"role": "assistant", "content": "markdown ingest still running (pid 48213, elapsed 00:22:40); "
                                             "5,010 files indexed so far."},
            {"role": "user", "content": "Also, house rule you should know: every new vector-store provider needs "
                                        "a test directory under tests/vector_stores/ before the PR can merge. "
                                        "Reviewers reject without it and it's not in the contributing guide."},
            {"role": "assistant", "content": "markdown ingest still running (pid 48213, elapsed 00:24:11); "
                                             "5,402 files indexed so far."},
        ],
        "label": "extract",
        "expect_type": "convention",
        "note": "MIXED: undocumented team rule between two ingest heartbeats.",
    },
]


FIXTURES: list[dict] = [*_DROP, *_EXCLUDE, *_EXTRACT]


def by_label(label: str) -> list[dict]:
    """All fixtures carrying `label`."""
    return [f for f in FIXTURES if f["label"] == label]


def counts() -> dict[str, int]:
    """Fixture count per label, so the harness can report its own coverage."""
    return {label: len(by_label(label)) for label in LABELS}


def counts_by_type() -> dict[str, int]:
    """Extract-fixture count per expected memory type."""
    out: dict[str, int] = {}
    for f in by_label("extract"):
        t = f["expect_type"] or "unspecified"
        out[t] = out.get(t, 0) + 1
    return out


def get(fixture_id: str) -> dict | None:
    return next((f for f in FIXTURES if f["id"] == fixture_id), None)


def coverage_line() -> str:
    c = counts()
    types = ", ".join(f"{k}={v}" for k, v in sorted(counts_by_type().items()))
    return (f"{len(FIXTURES)} fixtures: drop={c['drop']} exclude={c['exclude']} extract={c['extract']} "
            f"({types})")


if __name__ == "__main__":  # `python3 eval/fixtures.py` prints coverage
    print(coverage_line())
