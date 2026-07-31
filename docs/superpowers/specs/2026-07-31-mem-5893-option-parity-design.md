# MEM-5893: Platform option parity across SDKs and CLIs

Status: proposed
Date: 2026-07-31
Linear: [MEM-5893](https://linear.app/mem0/issue/MEM-5893)

## Problem

Mem0 Platform ships features faster than its clients expose them. A documented
feature can be unreachable from the surface a user actually holds.

Deshraj hit this directly: the CLI cannot pass `custom_instructions`, and cannot
pass `show_expired` or `reference_date` on search.

The gap is wider than the ticket says. Four client surfaces (Python SDK, TS SDK,
Python CLI, Node CLI) have each drifted from the v3 REST API in a different
direction, and from each other.

## Verified coverage matrix

Measured against `docs/openapi.json` and live calls to `api.mem0.ai` on
2026-07-31. Every cell was probed, not inferred.

| v3 param | Py SDK typed | Py SDK works | TS SDK | Py CLI | Node CLI |
|---|---|---|---|---|---|
| `custom_instructions` | yes | yes | yes | **no** | **no** |
| `custom_categories` | yes | yes | yes | **broken** | **broken** |
| `structured_data_schema` | yes | yes | yes | **no** | **no** |
| `timestamp` | yes | yes | yes | **no** | **no** |
| `reference_date` | **no** | yes (kwargs) | **no, blocked** | **no** | **no** |
| `show_expired` | yes | yes | yes | **no** | **no** |
| `latest_only` | **no** | yes (kwargs) | yes | **no** | **no** |
| `delete_linked` | yes | yes | yes | **no** | **no** |
| `keyword_search` | **no** | yes (kwargs) | **no, blocked** | yes | yes |
| `expiration_date` | yes | yes | yes | yes (add only) | yes (add only) |
| `rerank` | yes | yes | yes | yes | yes |

Two structural facts drive the whole design:

1. **`MemoryClient._prepare_params` is a pure passthrough.** It drops `None` and
   forwards every other kwarg verbatim. The Python SDK is therefore
   *functionally complete* for every v3 param. Its gaps are type hints only, so
   they cost discoverability and IDE autocomplete, never capability.

2. **TS SDK option interfaces are closed.** `SearchMemoryOptions` has no index
   signature, so an unlisted param is a compile error, not a passthrough.
   Confirmed: `referenceDate` produces `error TS2353`. TS users have no
   workaround short of dropping to raw `fetch`.

That asymmetry means Python needs typing and TS needs unblocking. They are not
the same task.

## Confirmed bug: `--categories` is a silent no-op

Not in the original ticket. Found while testing.

Both CLIs' `add` accepts `--categories` and sends payload key `categories`. The
v3 add schema and both SDKs use `custom_categories`, shaped as a list of
objects (`[{"name": "description"}]`), not a list of strings.

The v3 add endpoint returns HTTP 200 for unrecognized top-level keys, verified
with a deliberate `totally_bogus_key` control, so the mismatch never surfaces as
an error.

Proof, single request carrying three flags:

```
mem0 add ... --metadata '{"src":"mem5893"}' --expires 2027-12-31 --categories "health,travel"
  metadata        -> {'src': 'mem5893'}   landed
  expiration_date -> 2027-12-31           landed
  categories      -> None                 silently dropped
```

Identical result in both CLIs. The command reports success while discarding
input, which is worse than the flag being absent.

Caveat, stated so nobody over-claims the root cause: a control request sending
the correct `custom_categories` key also returned `categories: null` on this
project. The no-op is proven; the key mismatch is the probable but not yet
confirmed cause. **Confirm with the platform team before shipping the fix**, since
if the backend also ignores `custom_categories` on this path, renaming the key
alone will not restore the feature.

Note that `categories` *is* a legitimate filter on search and get_all. It was
only ever wrong on `add`.

## Non-goals

Deliberately excluded to keep one reviewable theme, "every v3 option is
reachable from every surface":

- New CLI commands: `history`, `feedback`, `export`, `batch`. These are absent
  from both CLIs (zero references) and all four endpoints are live. They are
  new features, not option parity. Follow-up ticket.
- Project-level settings in the CLI (`decay`, `memory_depth`, `multilingual`).
- Graph memory (`enable_graph`), webhooks, multimodal.
- Any OpenAPI-driven codegen or shared schema layer. See Rejected below.

## Rejected approach: generate clients from OpenAPI

The obvious reaction to "four surfaces drifted" is to generate them from
`docs/openapi.json` so they cannot drift again.

Rejected. It rewrites four shipping clients across two languages to fix roughly
twenty missing field declarations, and each CLI has hand-tuned ergonomics
(`--expires` reading nicer than `--expiration-date`, comma-or-JSON parsing,
Rich and Commander output) that a generator flattens. The cure is an order of
magnitude larger than the disease.

Taken instead: add the missing fields by hand, then add one cheap drift test so
the next omission fails in CI rather than in a Slack thread.

## Design

### 1. TS SDK, unblock (highest severity, smallest diff)

`mem0-ts/src/client/mem0.types.ts`, add to `SearchMemoryOptions`:

```ts
referenceDate?: string | number;
keywordSearch?: boolean;
```

No other change. `camelToSnakeKeys` already converts these correctly, and
neither is an opaque-value key, so `OPAQUE_VALUE_KEYS` stays untouched.

### 2. Python SDK, type what already works

`mem0/client/types.py`. Purely additive, no runtime behavior change, since
these already reach the API through `**kwargs`.

- `SearchMemoryOptions`: `reference_date`, `latest_only`, `keyword_search`
- `GetAllMemoryOptions`: `latest_only`

### 3. Both CLIs, add the missing flags

Applied identically to `cli/python` and `cli/node`, which are currently
option-for-option identical and must stay that way.

| Command | New flag | Payload key |
|---|---|---|
| `add` | `--custom-instructions <text>` | `custom_instructions` |
| `add` | `--custom-categories <json>` | `custom_categories` |
| `add` | `--structured-data-schema <json>` | `structured_data_schema` |
| `add` | `--timestamp <unix>` | `timestamp` |
| `search` | `--show-expired` | `show_expired` |
| `search` | `--reference-date <date>` | `reference_date` |
| `search` | `--latest-only` | `latest_only` |
| `list` | `--show-expired` | `show_expired` |
| `list` | `--latest-only` | `latest_only` |
| `update` | `--expires <date>` | `expiration_date` |
| `update` | `--timestamp <unix>` | `timestamp` |
| `delete` | `--delete-linked` | `delete_linked` |

JSON-valued flags follow the existing `--metadata` precedent: parse with the
shared JSON helper, exit 1 with a clear message on malformed input.

`--reference-date` accepts `YYYY-MM-DD` or a Unix epoch, matching the v3 schema
which types it as permissive.

### 4. Fix `--categories` on add

Pending the platform-team confirmation noted above:

- Remove `--categories` from `add`. It has never worked, so no behavior anyone
  relies on is lost.
- `--custom-categories <json>` replaces it with the correct key and shape.
- Passing `--categories` to `add` exits 1 pointing at `--custom-categories`,
  rather than being silently accepted. A flag that used to lie should not
  become a flag that silently disappears.
- `list --category` is untouched. It is a real filter and works today.

### 5. Drift test, one per language

The check that stops this recurring. Not an abstraction, a test.

Read the v3 request schemas from `docs/openapi.json`, assert every documented
param for add / search / get_all is reachable on each surface in that language:
option model fields for the SDK, registered flag names for the CLI. A param
deliberately not surfaced goes in an explicit `KNOWN_UNSURFACED` set with a
reason, so skipping is a visible decision rather than an accident.

- Python: `cli/python/tests/test_option_parity.py`, pytest
- TS: `cli/node/src/__tests__/option-parity.test.ts`, vitest

This is the piece that makes the audit unnecessary next time.

## Testing

Every change is a param reaching the API, so tests assert on the built payload
rather than mocking transport.

- **Unit, both CLIs**: each new flag produces its key in the request payload;
  each JSON flag rejects malformed input with exit 1; `add --categories` exits 1
  with the redirect message.
- **Unit, both SDKs**: new typed options serialize to the right snake_case key.
  TS additionally gets a compile-level assertion that `referenceDate` and
  `keywordSearch` are accepted, the inverse of the `TS2353` probe that found the
  bug.
- **Regression, the bug**: an `add` carrying metadata, expiration and custom
  categories together asserts all three land. This is the exact shape that
  failed, and it fails today.
- **Manual, two isolated instances**: the harness used for this audit. Separate
  `HOME` per sandbox, since both CLIs hardcode `~/.mem0` with no env override.
  Run the full CRUD lifecycle plus every new flag against `api.mem0.ai`, then
  delete the scoped test users.

## Risks

- **`custom_categories` may be ignored backend-side on this path**, per the
  caveat above. Blocks item 4 only. Resolve before merge; the rest of the PR is
  independent of it.
- **Cross-language drift during review.** Both CLIs must land the same twelve
  flags with the same names. The drift test in item 5 catches an omission in
  either.
- **`--timestamp` and `--structured-data-schema` are in the SDKs but not the
  documented v3 add schema.** Surface them, and confirm they are supported
  rather than vestigial before documenting them as CLI features.

## Delivery

One PR, per request, spanning `mem0/`, `mem0-ts/`, `cli/python/`, `cli/node/`.

Suggested commit order so review can proceed section by section, and so the
blocker can be cherry-picked if the PR stalls on the `custom_categories`
question:

1. TS SDK unblock, item 1
2. Python SDK typing, item 2
3. CLI flags, item 3, both CLIs in one commit to keep them visibly in sync
4. `--categories` fix, item 4
5. Drift tests, item 5

Docs: `docs/open-source/cli.mdx` (or the CLI reference page) needs the new
flags. Any new `.mdx` must be registered in `docs/llms.txt`, enforced by
`docs-llms-txt-check.yml`.
