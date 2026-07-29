# mem0-agent

Coding memory for Claude Code and friends, built on the [Mem0](https://mem0.ai) platform.

It remembers the things that change how an assistant should behave next time — your
preferences, the decisions you made and why, the team conventions that live nowhere in
the repo, the gotchas you root-caused, the procedures you verified. It deliberately does
not remember what you did today.

Zero runtime dependencies (stdlib only; `keyring` is optional). Every hook fails open —
if the API is down, your session is unaffected.

## Install

```bash
pip install 'mem0-agent[keyring]'      # keyring extra stores the API key in the OS keychain
mem0-agent onboard                     # asks for a key, picks a memory mode, pushes project config
```

Onboarding never reads your shell rc files and never writes a key into a `.env`. The key
comes from `MEM0_API_KEY` or the OS keychain; a key you type at the prompt goes to the
keychain and nowhere else. Get one at <https://app.mem0.ai/dashboard/api-keys>.

To wire the hooks into Claude Code, point your plugin/settings config at the generated
manifest:

```
hooks/hooks.json
```

Non-interactive install (CI, dotfiles, provisioning):

```python
from mem0_agent.onboard import run_onboard
run_onboard(interactive=False, memory_mode="dual", capture="conservative")
```

## The two memory modes

Chosen once per project at onboard, stored per project in `~/.mem0/v2/settings.json`.
The default is DUAL when the repo already has memory files (`CLAUDE.md`, `AGENTS.md`,
`.cursorrules`, `MEMORY.md`, `.claude/memory/`), FULL when it has none.

| | DUAL | FULL |
|---|---|---|
| Repo memory files | authoritative for repo-local notes | not used |
| mem0 holds | durable, cross-machine, cross-repo knowledge | everything |
| MEMORY.md write-blocker | off | on |
| Native auto-memory | leave it on | turn it off |

DUAL is the honest default for a repo that already documents itself: two memory layers
that each know their job. FULL is for people who want one place to look, and it installs
a write gate so the assistant stops appending to `MEMORY.md` behind your back.

Change it later:

```bash
mem0-agent config set memory_mode dual|full
```

## The two aggressiveness dials

```bash
mem0-agent config set capture   conservative|balanced|aggressive
mem0-agent config set retrieval conservative|balanced|aggressive
```

- **capture** — how eagerly a moment becomes a candidate memory. `conservative` stores
  only explicit "remember this" style signals; `aggressive` also stores inferred
  decisions and conventions.
- **retrieval** — how much context is injected at session start (roughly 600 / 1500 /
  2500 characters) and how confident an error match must be before it is surfaced.
  `conservative` disables error assist entirely.

## How the write gate works

Nothing is stored just because it happened. A candidate has to survive three gates:

1. **Trigger** — a local, network-free detector on `UserPromptSubmit` decides whether the
   moment is even a candidate. This runs on the hot path of every turn, so it is
   local-only by contract and enforced with `MEM0_LOCAL_ONLY=1` in the generated hook.
2. **Turn boundary** — candidates are buffered and judged at `Stop`, `PreCompact` and
   `SessionEnd`, when it is finally clear how the turn ended. One turn costs at most one
   write, and all three writes are backgrounded so they are never on your critical path.
3. **Platform policy** — the project's custom instructions are the real gate. They name
   the six types (`preference`, `decision`, `convention`, `insight`, `runbook`,
   `session_state`) and explicitly exclude progress updates, status heartbeats, file and
   commit lists, repo file contents, session-only facts, one-off instructions and
   secrets. `mem0-agent onboard` pushes them and verifies the round-trip; the policy
   version is stamped into every memory's metadata so a quality regression can be traced
   back to the revision that caused it.

Reads are pinned to the project and always `latest_only`, so a superseded memory never
comes back beside the one that replaced it.

## Hooks are generated, not hand-written

`hooks/hooks.spec.yaml` is the single source of truth. It declares each hook's event,
matcher, command, timeout, background/blocking flags, local-only contract, and one line
of *why*.

```bash
python3 hooks/generate.py           # write hooks/hooks.json
python3 hooks/generate.py --check   # exit 1 if the committed manifest drifted (run in CI)
```

| Event | Matcher | Command | Behavior |
|---|---|---|---|
| SessionStart | `startup\|resume\|compact` | `context` | blocking, injects project knowledge + open threads |
| UserPromptSubmit | — | `observe --source prompt` | blocking, **local-only, no network** |
| PostToolUse | `Bash` | `assist-error` | detached; a hit lands in the session buffer |
| Stop | — | `flush` | detached |
| PreCompact | — | `flush --reason precompact` | detached |
| SessionEnd | — | `flush --reason end` | detached |

Cursor, Codex and Antigravity are declared in the spec as unsupported rather than
deleted, so the gap stays visible instead of turning back into a hand-maintained file.

## Why v2

v1 wrote roughly **98 memories a day**, and almost all of it was heartbeat spam: "started
task X", "80% complete", "modified 3 files", "opened PR #123" — activity you can already
get from git, restated in a memory store where it drowned out the things you actually
wanted back. Retrieval got worse the longer you used it.

v2 targets **under 15 memories a day**, all durable knowledge. The changes that get it
there:

- The write gate above, validated against the real polluted v1 corpus.
- Writes at turn boundaries in batches, instead of one write per tool call.
- No network call on the per-prompt hot path.
- Session state per session ID under `~/.mem0/v2/`, not `/tmp` keyed by `$USER`, so
  concurrent sessions stop corrupting each other's counters.
- Project and org pinned in the request body, so coding memories can no longer leak into
  whatever project the API key happens to default to.
- One hook spec, generated manifests, drift caught by CI.

## License

Apache-2.0
