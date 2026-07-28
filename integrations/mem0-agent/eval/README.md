# Write-gate evaluation

The v1 plugin had no way to measure extraction quality, so it degraded for three months
without anyone noticing. When the corpus was finally audited, 20.5% of it was
near-duplicate heartbeats — the largest single cluster was 119 near-identical
training-progress frames — and organic searches had fallen from 257/month to 75/month.
The memory got noisy, people stopped trusting it, and nothing in the system said so.

This directory is the instrument that would have said so. It scores the write gate
against a labeled fixture set and fails a build when the score regresses.

The gate has two halves, and each mode measures one of them:

| Half | Where it lives | Measured by |
| --- | --- | --- |
| Local trigger rules — mechanical noise never leaves the machine | `src/mem0_agent/triggers.py` | `--offline` |
| Custom instructions — the platform stores nothing from a narration/activity/repo-file window | `src/mem0_agent/config/project_config.py` (`INSTRUCTIONS`) | `--live` |

## Running it

### Offline (default, no network, no credentials)

```bash
cd integrations/mem0-agent
PYTHONPATH=src python3 eval/run.py --offline
PYTHONPATH=src python3 eval/run.py --offline --level aggressive   # sweep a capture level
PYTHONPATH=src python3 eval/run.py --offline --check              # exit non-zero on regression
```

Runs all fixtures through `mem0_agent.triggers.classify` and scores the decisions
against the labels. It costs nothing, so it belongs in CI on every commit that touches
`triggers.py`.

`triggers.py` is imported lazily. If it is missing or its `classify()` signature is
unreadable, the run reports the reason and scores nothing rather than crashing — but
`--check` then exits non-zero, because a gate that cannot measure must not pass.

### Live (writes to a scratch project)

```bash
export MEM0_API_KEY=...
PYTHONPATH=src python3 eval/run.py --live \
  --project-id proj_SCRATCH --org-id org_YOURS --cleanup --check
```

Replays every `exclude` and `extract` fixture through `mem0_agent.api.Api` with
`infer=True`, waits for extraction, reads back, and scores what the platform actually
stored. This is the only way to test the custom instructions; they are a prompt, and
prompts are not unit-testable.

Safety and correctness properties, each of which exists because of something that went
wrong before:

- **`--project-id` and `--org-id` are required and have no defaults.** A live run writes
  real memories. v1's benchmark data ended up in the production project because a
  harness defaulted to whatever the API key resolved to. Point these at a scratch
  project.
- **Every fixture gets its own user id**, `eval-<runid>-<fixture id>`, under app id
  `eval-<runid>`. Results are attributable to a fixture and a run, and anything left
  behind is trivially findable.
- **It polls; it does not sleep.** Extraction landed anywhere between 20s and 5min
  during validation, so any fixed wait is either wrong or wasteful. `--timeout`
  (default 360s) bounds the wait; `--min-settle` (default 60s) is the minimum time
  before a zero read is allowed to count as suppression, since "nothing stored" and
  "not stored yet" look identical.
- **It scores `metadata.type`, never `categories`.** Platform categorization lags ~3.9h
  at the median and is 0% for memories under an hour old, so a category-based score
  would read zero on a fresh run and tell you nothing.
- **`--cleanup` deletes everything the run wrote.** Without it the report prints the
  `app_id` and user-id prefix needed to clean up by hand.

One honesty caveat on the live `type_match` metric: `metadata.type` is stamped by the
*client* at write time (from `triggers.classify` when available, otherwise from the
fixture's `expect_type`). So `type_match` measures that the type survives the round
trip, and — when the classifier is present — that the classifier chose the right one.
It is not the platform's independent opinion. The report records `stamped_by` per
fixture so a reader can tell which case they are looking at.

Both modes write `eval/last_report.json`: every score, every per-fixture row, the
thresholds in force, and the pass/fail verdict.

## The fixture set

`fixtures.py` holds the labeled windows. Each entry is exactly:

```python
{"id": str, "window": [{"role", "content"}, ...], "label": "drop"|"exclude"|"extract",
 "expect_type": str | None, "note": str}
```

| Label | Contract | Enforced by |
| --- | --- | --- |
| `drop` | Must never be sent to the platform at all | client trigger rules |
| `exclude` | May be sent, but the platform must store nothing from it | custom instructions |
| `extract` | Must produce ≥1 memory, ideally of `expect_type` | both halves |

The `drop` and `exclude` windows use the wording of the audited v1 corpus: the
epoch/loss/ETA training heartbeat, the `N of M chunks processed (X%)` frame, the
markdown-ingest `pid`/`elapsed` line, monitoring status lines, tool-only turns,
assistant narration, file-modification lists, `CLAUDE.md`/README excerpts, one-off
directives (`you do it`), and session-only status (`at 12:45:24 the job was wrapping
up`). Several noise classes appear two or three times with only the numbers changed —
that is what a near-duplicate cluster actually looks like, and a gate that catches the
first frame but not the third has learned the numbers rather than the shape.

The `extract` block covers all five durable types plus four **mixed** windows, where a
durable fact sits between two progress lines. Mixed windows are the most informative
fixtures in the set: they fail in both directions. A gate too eager to drop heartbeats
destroys the fact along with them; a gate too eager to store keeps the heartbeats.

Print coverage at any time:

```bash
python3 eval/fixtures.py
```

## Thresholds

`--check` exits non-zero when a gated metric falls below its floor:

| Metric | Floor | Why |
| --- | --- | --- |
| `hard_drop_recall` | 0.95 | Fraction of `drop` fixtures the client never sends. This is the number that was silently 0 in v1. |
| `extract_recall` | 0.80 | Fraction of `extract` fixtures that survive. Offline: flagged for capture. Live: ≥1 memory stored. A gate that stores nothing scores perfectly on noise. |

Both floors must hold; they measure opposite failure directions and either one alone is
trivially gamed.

Other metrics are reported but not gated, because they diagnose rather than decide:

- `hard_drop_explicit` — how much of the noise containment comes from a real drop rule
  rather than from no flag rule happening to match. `capture.py` only forwards windows
  whose action is `flag`, so a `skip` does contain the noise — but only until someone
  adds a flag rule that matches it. A gap between `hard_drop_recall` and
  `hard_drop_explicit` is a list of heartbeats held back by luck.
- `hard_drop_precision` — of everything hard-dropped, how much was safe to drop. This is
  where over-broad drop rules show up, and it is the metric the mixed fixtures exist to
  move. A hard drop on an `extract` window is the one unrecoverable error: the memory is
  gone and nothing logs a miss. Hard-dropping an `exclude` window is *not* counted
  against this score — those are meant to be discarded, and discarding them locally is
  simply cheaper than having the platform do it.
- `extract_skipped` vs `extract_hard_dropped` — same lost memory, different repair. A
  skip means a flag rule is missing; a hard drop means a drop rule is too greedy.
- `flag_precision`, `type_accuracy`, `type_coverage`, `exclude_suppression`,
  `noise_leak_count` — the rest of the picture.

`noise_leak_count` deserves a note: it regex-matches stored memory text for heartbeat
markers (`epoch`, `ETA`, `N% complete`, `chunks processed`, `pid NNNN`, …). Any hit
means the class that ate 20.5% of the v1 corpus has found a new way through, even if
every count-based score looks fine.

Raising a floor is cheap and should be done once a score has held above the new bar for
a while. Lowering one is a decision that belongs in a PR description, next to the reason.

## Baseline (design validation)

Established against the live platform during the v2 design phase, using the same
fixture wording:

- **Exclude classes: 5 of 6 suppressed by the custom instructions alone.** Training
  heartbeats, chunk-progress frames, file-modification lists, session-only status, and
  assistant narration all stored nothing.
- **The repo-file class is client-side only.** A pasted `CLAUDE.md` excerpt produced
  three confident "preference" memories. This is not fixable by prompting: a pasted
  convention and a stated convention are textually identical, so the extractor is right
  to store it and the client must never send it. `triggers.py` owns this rule, and it is
  mandatory rather than tunable.
- **Extract classes: 5 of 5 captured** — preference, decision, convention, insight and
  runbook — plus the mixed window, where the bastion-host fact was stored and neither
  surrounding progress line was.
- **Categories were empty on every memory** at read time, which is what fixed the read
  path on `metadata.type` and this harness with it.

Write latency was 0.38–0.51s for the fire-and-forget `add`; extraction landed 20s–5min
later. That gap is the whole reason the live mode polls.

## Adding a fixture

1. Append it to `_DROP`, `_EXCLUDE` or `_EXTRACT` in `fixtures.py` with a fresh `id`.
2. Use real wording. A fixture invented to be easy to classify measures nothing —
   prefer a window copied from an actual session or an audit.
3. Write a `note` saying which failure the fixture guards. Six months from now that
   sentence is the only thing standing between a red score and someone "fixing" it by
   deleting the fixture.
4. `extract` fixtures need an `expect_type` from
   `mem0_agent.config.project_config.TYPES`; `drop` and `exclude` fixtures must have
   `expect_type = None`.
5. Run `PYTHONPATH=src python3 -m pytest tests/test_fixtures.py -q` — it enforces the
   schema, unique ids, valid labels and types, and that every durable type is covered.
6. Re-run `--offline` and, when the change touches the instructions, `--live`.

Adding a fixture usually lowers a score. That is the point: the score was previously
measuring a smaller world.
