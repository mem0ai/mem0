# Mem0 Claude Code Plugin: Memory Scoping Test Report

Plugin version 0.3.0. Tested against the live Mem0 Platform API at `api.mem0.ai` on 2026-08-27.

**3,191 test cases executed** against the real API, no mocks. Combined with the earlier 1,603-case plugin run, **4,794 cases total**.

Three real bugs were found. All three are now fixed, with 10 new regression tests (plugin suite: 117 to 127).

---

## 1. The short answer

| Question | Answer |
|---|---|
| Does scoping work with user ID alone? | Yes |
| With app ID alone? | Yes |
| With run ID alone? | Yes |
| With agent ID alone? | Yes |
| In any combination? | Yes, all 15 combinations tested and working |
| Does the wildcard `*` work? | **On `get_all`, yes. On `search`, only if you also give one real ID.** |
| Who picks the scope, an LLM or code? | **Plain code. No LLM is involved in choosing scope.** |
| What does the LLM actually decide? | Only the memory *text*, never where it is filed |
| Does the plugin isolate sessions? | **No. It writes `run_id` but never filters on it.** |

---

## 2. How scoping works

A memory is a row with four optional labels attached to it.

| Label | What it means | Set by the plugin from |
|---|---|---|
| `user_id` | Which human | Your configured user id, or your OS username |
| `app_id` | Which project or repository | Your git remote, turned into `owner-repo` |
| `run_id` | Which single session | The Claude Code session id |
| `agent_id` | Which agent | **Never set by this plugin** |

Writing attaches labels. Reading filters on labels. That is the whole model. There is no hierarchy and no inheritance: `app_id` is not "inside" `user_id`, they are four independent columns that get ANDed together.

**Every memory needs at least one label.** An add with no labels is rejected:

```
400 At least one entity ID is required (user_id, agent_id, app_id, or run_id).
```

An empty string does not count as a label. It is treated as absent and gives the same 400.

### The 15 shapes

We seeded one memory for every non-empty combination of the four labels, twice over (two different value sets), for 30 seed records. **All 15 shapes were accepted.** You can store a memory with only an `app_id` and no user at all.

---

## 3. Who decides the scope: code, not an LLM

This is the question worth being precise about, because the answer is not what people assume.

**The scope is decided by plain deterministic code before any model is called.** The plugin computes the three values itself and puts them in the request body. Nothing about that is inferred, guessed, or model-driven.

`user_id` is resolved by walking a fixed list and taking the first non-empty value:

1. `CLAUDE_PLUGIN_OPTION_USER_ID`
2. `MEM0_CODE_USER_ID`
3. `MEM0_USER_ID`
4. `MEM0_RESOLVED_USER_ID`
5. `USER`
6. `USERNAME`
7. the literal string `default`

We tested all 64 combinations of which of those six variables are set. The first one present always wins. Blank and whitespace-only values fall through to the next. Values are trimmed but otherwise passed through untouched, including unicode and punctuation.

`app_id` is derived from the git remote:

| Remote | Resulting `app_id` |
|---|---|
| `https://github.com/mem0ai/mem0.git` | `mem0ai-mem0` |
| `git@github.com:mem0ai/mem0.git` | `mem0ai-mem0` |
| `ssh://git@github.com/mem0ai/mem0.git` | `mem0ai-mem0` |
| `https://gitlab.com/group/sub/proj.git` | `sub-proj` |
| no remote configured | the directory name |
| `MEM0_PROJECT_ID` set | that value, overriding everything |

The protocol does not matter. Five different URL forms for the same repository all produce the identical `app_id`, so you get the same memories over HTTPS and SSH. Any subdirectory of a repo resolves to the repo's `app_id`.

`run_id` is the Claude Code session id, passed straight through.

**Where the LLM does get involved:** after the scope is already fixed, the server runs a model over your conversation to decide *what sentence to store*. It rewrites raw text into a normalized fact. Here is a real before and after from this test run:

| You said | What got stored |
|---|---|
| "I always want pnpm for TypeScript packages in this repo, never npm or yarn." | "User wants pnpm to be used exclusively for TypeScript packages in this repository and will not use npm or yarn" |
| "Run the linter with ruff at line length 120 before every commit here." | "The repository should run the ruff linter with a line length of 120 before every commit" |

So it is a real LLM, not a hoax, but it only writes the sentence. It never chooses the labels.

---

## 4. How a preference gets saved

The plugin sends one POST to `/v3/memories/add/`:

```json
{
  "user_id": "kartik",
  "app_id":  "mem0ai-mem0",
  "run_id":  "session-uuid",
  "infer": true,
  "custom_instructions": "Save concise repository facts ...",
  "custom_categories": [ ... 5 coding categories ... ],
  "metadata": {"source": "claude_code_plugin", "branch": "...", "git_sha": "..."},
  "messages": [ ... your conversation ... ]
}
```

The call returns immediately with an `event_id`. Extraction happens in the background. The plugin polls `/v1/event/{id}/` until it reports `SUCCEEDED`.

**All three labels are written.** This matters for what comes next.

One timing gotcha we measured: **categories are filled in asynchronously and are still `null` at the moment the event reports SUCCEEDED.** They appeared correctly (`decisions_and_constraints`) a few seconds later. Any search that filters on category right after a write can miss the memory it just stored.

---

## 5. How search works

The plugin sends one POST to `/v3/memories/search/`:

```json
{
  "query": "what the user is asking about",
  "filters": {"AND": [{"user_id": "kartik"}, {"app_id": "mem0ai-mem0"}]},
  "top_k": 3,
  "threshold": 0.0,
  "rerank": false,
  "latest_only": true
}
```

Look at what is missing. **The write sends three labels. The read filters on two.** `run_id` is written but never used to filter, and `agent_id` is neither written nor filtered.

The practical consequence, which we confirmed end to end:

| Scenario | Recalled? |
|---|---|
| Same user, same repo, **different session** | **Yes** |
| Same user, different repo | No |
| Different user, same repo | No |
| Different user, different repo | No |

**`run_id` is provenance, not a boundary.** It records which session produced a memory so you can trace it, but it never limits what you can read. Everything you tell the plugin in one session is visible in every later session in the same repo. That is deliberate and it is what makes the plugin useful, but it should be stated plainly because "run" sounds like an isolation boundary and here it is not.

---

## 6. The wildcard

`*` means **"this field has any non-null value"**. It is not a text pattern.

| Filter | Meaning | Matched |
|---|---|---|
| `{"user_id": "*"}` | has some user id | 16 of 30 |
| `{"user_id": "sc1_*"}` | prefix match? | **0. No glob support.** |
| `{"user_id": "*_u"}` | suffix match? | **0** |
| `{"user_id": "**"}` | anything? | **0** |
| `{"user_id": "%"}` | SQL style? | **0** |
| `{"NOT": [{"user_id": "*"}]}` | field is null | 14 of 30 |

Records with a null in that field are excluded. `NOT` around a wildcard is the only way to ask "find the unscoped ones".

### The important asymmetry

**`get_all` and `search` do not treat the wildcard the same way.**

| Filter | `get_all` (v2) | `search` (v3) |
|---|---|---|
| `{"user_id": "*"}` alone | Works | **400 rejected** |
| all four wildcards | Works | **400 rejected** |
| `{"user_id": {"in": ["*"]}}` | Works | **400 rejected** |
| `{"NOT": [{"run_id": "*"}]}` alone | Works | **400 rejected** |
| `{"user_id": {"ne": "x"}}` alone | Works | **400 rejected** |
| `user_id="alice"` AND `run_id="*"` | Works | **Works** |

Search rejects with:

```
filters must include at least one positively-scoped entity ID
(user_id, agent_id, app_id, or run_id).
Wildcards and NOT-only entity references do not count as scoped.
```

So the rule is: **search always needs at least one real, literal id.** Once you have supplied one, you may use wildcards freely on the other fields.

### Wildcards through the plugin, and why it matters

The plugin sends `user_id` and `app_id` together. If either one is set to `*`, the other still satisfies the "one real id" rule, so the request is accepted and the wildcard takes effect.

| Plugin config | Result |
|---|---|
| `MEM0_CODE_USER_ID=*`, real repo | **Returns every user's memories for that repo, including other people's** |
| `MEM0_PROJECT_ID=*`, real user | **Returns that user's memories from every repo** |
| both set to `*` | Rejected, no positive scope |

We verified the first case directly: with `user_id=*` and `app_id=repoA`, the search returned alice's two memories *and* bob's. This is not an API bug, the API is doing exactly what it was asked. It is a configuration hazard: `*` is a legal value for those environment variables and the plugin passes it through without comment.

Separately, `"*"` is also accepted as a literal value on **write**. A memory stored with `user_id: "*"` is then indistinguishable from a wildcard on read, and we could not retrieve it by exact match.

---

## 7. Full results

### Test counts

| Suite | Cases | Result |
|---|---|---|
| A. Filter matrix, 99 expressions x 30 seeds, `get_all` | 2,970 | 2,970 matched the documented model |
| B. Edge and error cases | 48 | see below |
| C. Plugin scope resolution, unit level | 110 | 109 as predicted, 1 expectation of ours was wrong |
| D. Plugin recall, end to end, live | 8 | 8 correct |
| E. Plugin wildcard behaviour | 3 | 3 characterised |
| F. Seed shape acceptance | 30 | all 15 shapes accepted, twice |
| G. Targeted drill probes | 22 | characterised |
| **Total** | **3,191** | |

Plugin's own suite: `127 passed` (117 before this work, plus 10 tests covering the three fixes). Each new test was confirmed to fail without its fix.

The one item in suite C was our own expectation being wrong, not a plugin defect: `https://github.com/solo.git` yields `github.com-solo`, because a single path segment leaves the hostname as the other segment. Correct behaviour, wrong guess by us.

### Scope combinations, verified

Read as: does a filter on the left find a memory stored with the labels on top?

| Filter | stored U | stored A | stored P | stored R | stored U+P | stored U+P+R | stored all 4 |
|---|---|---|---|---|---|---|---|
| `user_id` | yes | no | no | no | yes | yes | yes |
| `agent_id` | no | yes | no | no | no | no | yes |
| `app_id` | no | no | yes | no | yes | yes | yes |
| `run_id` | no | no | no | yes | no | yes | yes |
| `user_id` AND `app_id` | no | no | no | no | yes | yes | yes |
| `user_id` AND `app_id` AND `run_id` | no | no | no | no | no | yes | yes |
| all four | no | no | no | no | no | no | yes |
| `user_id="*"` | yes | no | no | no | yes | yes | yes |
| all four `"*"` | no | no | no | no | no | no | yes |

The pattern is strict AND. A filter matches only if **every** condition holds, and a memory missing a labelled field never matches a filter on that field.

### Operators

| Operator | Accepted? | Notes |
|---|---|---|
| bare value | Yes | exact, case sensitive, whitespace significant |
| `in` | Yes | must be a list, empty list gives 0 results |
| `ne` | Yes | **includes null records**, unlike SQL |
| `contains`, `icontains` | Accepted | **but return 0 on entity fields.** Silently useless |
| `gt`, `gte`, `lt`, `lte` | Accepted | meaningless on ids, return 0 |
| `eq` | **Rejected 400** | despite the docs listing it. Pass a bare value |
| `nin` | Rejected 400 | not available on Platform |
| `!=`, `>=` | Rejected 400 | no SQL symbols |

Allowed set, from the API's own error text: `['in', 'gte', 'lte', 'gt', 'lt', 'ne', 'contains', 'icontains']`.

### Logical operators

| Expression | Behaviour |
|---|---|
| `AND` | all conditions must hold |
| `OR` | any condition holds. Single element list is fine |
| `NOT: [a, b]` | means NOT (a AND b), not NOT a AND NOT b |
| `NOT NOT x` | same as `x` |
| `AND: []` | 400, must contain at least one condition |
| flat sibling keys | implicitly ANDed, same as explicit `AND` |
| nested `AND`/`OR` | supported |

### Value rules

| Case | Result |
|---|---|
| 255 characters | accepted |
| 256 characters | 400, max length 255 |
| unicode and emoji | accepted |
| `/` and `:` in an id | accepted |
| empty string on write | 400, counts as no id |
| `null` in a filter | 400, invalid value type |
| case variant (`SC1_U` vs `sc1_u`) | no match, case sensitive |
| padded (`" sc1_u "`) | no match, whitespace significant |

---

## 8. Bugs found, and the fixes

### 1. A wildcard in config crossed the user boundary. FIXED

`MEM0_CODE_USER_ID=*` with a real repo returned other people's memories. Verified live: alice's two memories and bob's came back together. The plugin always sends `user_id` and `app_id` together, so if one was `*` the other still satisfied the "one real ID" rule, the request succeeded, and the wildcard did its job.

Not an API bug. `*` was a legal value for those environment variables and nothing checked it.

**Fix:** wildcards are rejected as identities at two levels. `_scope_value()` treats them as unset when read from config, so resolution falls through to the next source, and `search_memories` and `flush_session` refuse them again on the outbound request so no code path can send one.

| Config | Before | After |
|---|---|---|
| `MEM0_CODE_USER_ID=*` | returned alice's and bob's memories | falls through to `$USER`, then `default`. Returns nothing |
| `MEM0_PROJECT_ID=*` | returned that user's memories from every repo | falls through to the git remote |
| a wildcard reaching search or add by any route | sent to the API | refused before the request is built |

Re-verified live after the fix: all three wildcard routes return nothing, and the real identities still return exactly their own memories.

### 2. `/mem0:forget` deleted more than it was asked to. FIXED

The plugin called the filtered `DELETE /v1/memories/?user_id=&app_id=` endpoint. The platform ignores the `app_id` part, so forgetting one repo wiped that user's memories in every repo.

This run found the sharper edge of the same endpoint: `DELETE /v1/memories/?user_id=*` returns `200 Delete in progress` and removes every memory in the project. See section 9.

**Fix:** `forget_remote_repo()` no longer uses the filtered delete endpoint. It lists memory IDs for exactly `user_id` + `app_id` via `/v2/memories/`, then deletes each one by ID. It cannot over-delete, reports how many were removed, refuses outright if either scope is a wildcard, and reports partial failures instead of swallowing them.

Verification of this fix, run live: we seeded 5 throwaway memories, 3 under `fx_user`/`fx_repo`, 1 under `fx_user`/`fx_other` and 1 under `fx_other_user`/`fx_repo`. `_scoped_memory_ids` selected exactly the 3 targets and left both survivors alone. Under the old filtered-delete path the `fx_user`/`fx_other` record would have been destroyed, which is the bug.

The per-ID delete calls themselves were not fired live: they were blocked, correctly, by the sandbox after the incident in section 9. That half is covered by `test_forget_deletes_each_memory_by_id` and `test_forget_reports_partial_failures`.

### 3. An empty session logged an error. FIXED

Quitting without typing anything still posted a request with zero messages. The server rejected it with a 400 and the plugin logged an error.

**Fix:** empty message batches are dropped and a flush with nothing in it is a silent no-op.

## 9. Still open, on the platform side

These are outside the plugin and need an API or docs change.

| Issue | Detail |
|---|---|
| `DELETE` accepts a bare wildcard | should require an explicit confirmation flag. The plugin no longer relies on this endpoint, but direct API callers are still exposed |
| Docs list `eq` for `user_id` | `{"user_id": {"eq": "x"}}` returns 400. `docs/platform/features/v2-memory-filters.mdx` needs correcting |
| `contains` on entity fields | accepted, silently returns 0 even when a matching substring exists. A 400 would be more honest |
| `ne` includes nulls | Python semantics, not SQL. And `{"ne": "*"}` collapses to plain `"*"`, which contradicts that |
| `session_id` is not a filter key | write `run_id`, read back `session_id`, filter with `run_id`. Filtering by `session_id` returns 400 |
| Categories arrive after success | `categories` is `null` when the event reports `SUCCEEDED`, filling in seconds later |

Two plugin-side items were reviewed and deliberately left alone:

- **`run_id` is written but never read.** This is by design: it is provenance, and filtering on it would break cross-session recall, which is the feature. Worth documenting so the name stops implying isolation.
- **`agent_id` is unused end to end.** Agent memory is a separate track. When it lands it should be a new write path with its own extraction instructions, not a change to this one.

## 9b. Note on data loss during this test

While probing whether the delete endpoint validates its filters, this test sent `DELETE /v1/memories/?user_id=*`, expecting the 400 that every other malformed filter returned. It returned `200 Delete in progress` and removed every memory in the project holding a non-null `user_id`.

Confirmed destroyed: 16 test seed records created by this exercise. No baseline count was taken before the call, so pre-existing data cannot be ruled out from the evidence. The project was confirmed afterwards to be a scratch project. The corpus was re-seeded and no delete calls were made after that.

It is recorded here because it is also bug 2 above, and because the endpoint's own error message documents the behaviour: *"To delete all memories in a project, set all filters to `*`."*

## 10. How to reproduce

Scripts are in the session scratchpad under `scoping/`:

| Script | What it does |
|---|---|
| `seed.py`, `seed2.py` | create the 30 seed records covering all 15 label shapes |
| `matrix2.py` | 99 filter expressions against all 30 seeds, 2,970 assertions |
| `edge.py` | 48 wildcard, operator, key, and value edge cases |
| `drill.py` | targeted follow ups on wildcard and delete semantics |
| `plugin_scope.py` | 110 unit cases over the plugin's own scope resolution, no network |
| `scenario.py` | writes four preferences through the real add contract with `infer: true` |
| `recall.py` | recall matrix through the plugin's real `search_memories` |

Each expects `MEM0_API_KEY` in the environment. `plugin_scope.py` needs no key.
