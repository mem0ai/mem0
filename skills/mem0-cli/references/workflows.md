# Mem0 CLI Workflows

Practical recipes for using the mem0 CLI in scripts, pipelines, and agent loops.

---

## Piping Content via Stdin

The CLI reads from stdin when no text argument is provided and stdin is a pipe or a redirected file. This works with `add`, `search`, and `update`. It never reads stdin in `--json`/`--agent` mode for `add`, and Python also skips it there for `search` and `update`, so pass the text as an argument in agent mode.

**Stdin detection method:**
- Python: `os.fstat(sys.stdin.fileno())` is a FIFO or a regular file
- Node: `fs.fstatSync(0)` is a FIFO or a regular file

### Add from pipe

```bash
echo "I prefer dark mode" | mem0 add --user-id alice
```

### Pipe multi-line content

```bash
cat <<EOF | mem0 add --user-id alice
The user prefers dark mode in all applications.
They also like monospace fonts for code editing.
EOF
```

### Pipe from another command

```bash
git log --oneline -5 | mem0 add --user-id ci-bot --metadata '{"source":"git"}'
```

### Search from pipe

```bash
echo "preferences" | mem0 search --user-id alice
```

### Update from pipe

```bash
echo "Updated: prefers dark mode AND high contrast" | mem0 update abc-123-def-456
```

---

## File Import

Use `mem0 import` to bulk-load memories from a JSON file.

### Basic import

```bash
mem0 import memories.json --user-id alice
```

### File format

The file should be a JSON array where each item has a `memory`, `text`, or `content` field:

```json
[
  { "memory": "Prefers dark mode" },
  { "text": "Allergic to nuts", "metadata": { "source": "intake-form" } },
  { "content": "Uses VS Code", "user_id": "bob" }
]
```

Items may also carry `agent_id`. CLI-provided `--user-id` and `--agent-id` (or configured defaults) override per-item values. A single JSON object is treated as a one-item array, and items without `memory`, `text`, or `content` are counted as failed.

### Import with JSON output

```bash
mem0 import data.json --user-id alice -o json
```

Output:
```json
{
  "status": "success",
  "command": "import",
  "duration_ms": 3140,
  "scope": { "user_id": "alice" },
  "data": { "added": 42, "failed": 0 }
}
```

This is the Python CLI output. The Node CLI omits `scope` and writes the `Importing memories... n/n` progress line to stdout before the JSON, so its output cannot be piped to `jq`.

---

## Agent Mode for LLM Consumption

Use `--json` or `--agent` to get structured JSON output suitable for LLM tool calling or agent frameworks. Spinners and progress always go to stderr, keeping stdout clean. Put the flag before the subcommand so it works in both the Python and Node CLIs.

### Search with agent mode

```bash
mem0 --agent search "preferences" --user-id alice
```

Output (stdout):
```json
{
  "status": "success",
  "command": "search",
  "duration_ms": 187,
  "scope": { "user_id": "alice" },
  "count": 2,
  "data": [
    { "id": "mem-abc", "memory": "User prefers dark mode", "score": 0.95, "created_at": "2025-01-15T10:00:00Z", "categories": ["preferences"] },
    { "id": "mem-def", "memory": "User likes monospace fonts", "score": 0.82, "created_at": "2025-01-15T10:01:00Z", "categories": ["preferences"] }
  ]
}
```

### Add with agent mode

```bash
mem0 --json add "Uses Python 3.12" --user-id alice
```

### Error handling in agent mode

Errors also return valid JSON with `"status": "error"`:

```bash
mem0 --agent search "test" --user-id alice --api-key invalid
```

Output:
```json
{
  "status": "error",
  "command": "search",
  "error": "Invalid or expired API key.",
  "data": null
}
```

---

## JSON Output + jq

Use `--output json` (or `-o json`) for JSON output, then pipe to `jq` for processing. `search`, `get`, `add`, `update`, and `delete` print the raw API response. `list`, `status`, and `import` print the standard envelope instead, so read the results from `.data`. Piping `import` to `jq` works only with the Python CLI (Node writes its progress line to stdout ahead of the JSON).

### Extract just memory text

```bash
mem0 list --user-id alice --output json | jq '.data[] | .memory'
```

### Get memory IDs

```bash
mem0 list --user-id alice -o json | jq '.data[].id'
```

### Count memories

```bash
mem0 list --user-id alice -o json | jq '.count'
```

### Filter by category in jq

```bash
mem0 list --user-id alice -o json | jq '[.data[] | select(.categories[]? == "preferences")]'
```

### Extract search scores

```bash
mem0 search "tools" --user-id alice -o json | jq '.[] | {memory, score}'
```

---

## Bulk Operations

### Delete multiple memories by ID

```bash
# Get IDs, then delete each one
mem0 list --user-id alice -o json | jq -r '.data[].id' | while read id; do
  mem0 delete "$id" --force
done
```

### Bulk add from a text file (one memory per line)

```bash
while IFS= read -r line; do
  mem0 add "$line" --user-id alice
done < memories.txt
```

### Copy memories between users

```bash
mem0 list --user-id alice -o json | jq -r '.data[].memory' | while IFS= read -r mem; do
  mem0 add "$mem" --user-id bob
done
```

### Export all memories to a file

```bash
mem0 list --user-id alice -o json > alice_memories.json
```

### Paginate through all results

```bash
page=1
while true; do
  result=$(mem0 list --user-id alice -o json --page "$page" --page-size 100)
  count=$(echo "$result" | jq '.count')
  if [ "$count" -eq 0 ]; then
    break
  fi
  echo "$result"
  page=$((page + 1))
done
```

---

## CI/CD Patterns

### Store build context as a memory

```bash
mem0 add "Build #${BUILD_NUMBER} deployed ${APP_VERSION} to ${ENVIRONMENT} at $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --agent-id "ci-bot" \
  --metadata "{\"build_number\":\"${BUILD_NUMBER}\",\"version\":\"${APP_VERSION}\",\"env\":\"${ENVIRONMENT}\"}"
```

### Retrieve deployment history

```bash
mem0 search "deployment to production" --agent-id ci-bot -o json -k 10
```

### Check CLI connectivity in CI

```bash
if mem0 status -o json | jq -e '.data.connected' > /dev/null 2>&1; then
  echo "mem0 is connected"
else
  echo "mem0 connection failed" >&2
  exit 1
fi
```

### Non-interactive init in CI

```bash
mem0 init --api-key "$MEM0_API_KEY" --user-id ci-bot --force
```

Or simply use the environment variable (no init needed):

```bash
export MEM0_API_KEY="$MEM0_API_KEY"
mem0 add "CI run started" --user-id ci-bot
```

### Store test results

```bash
test_summary=$(cat test-results.txt | head -20)
mem0 add "$test_summary" --agent-id ci-bot --metadata '{"type":"test-results"}'
```

---

## Stdin Detection Details

The CLI reads from stdin only when ALL of these conditions are met:

1. No text argument was provided on the command line.
2. For `add`: no `--messages` and no `--file` flag.
3. stdin is a pipe or a redirected file (a plain non-TTY such as `/dev/null` does not count).
4. The CLI is not in `--json`/`--agent` mode (`add` in both CLIs, `search` and `update` in Python).

**This means:**
- `mem0 add --user-id alice` in an interactive terminal will NOT hang waiting for input. It exits 1 with "No content provided".
- `echo "text" | mem0 add --user-id alice` will read "text" from stdin.
- `mem0 add "explicit text" --user-id alice` will use the explicit text, even if stdin is piped.

**Reading method:**
- Python: `sys.stdin.read().strip()`
- Node: `fs.readFileSync(0, "utf-8").trim()`

---

## Common Shell Patterns

### Error handling with exit codes

```bash
set -e  # Exit on error

mem0 status -o json | jq -e '.data.connected' > /dev/null

# Add with error check
if mem0 add "test memory" --user-id alice 2>/dev/null; then
  echo "Memory added successfully"
else
  echo "Failed to add memory" >&2
  exit 1
fi
```

### Capture memory ID from add

Default adds are asynchronous and return an `event_id`. Use `--no-infer` for a synchronous add whose `.data[0].id` is the memory id.

```bash
event_id=$(mem0 --agent add "new fact" --user-id alice 2>/dev/null | jq -r '.data[0].event_id // empty')
for _ in $(seq 30); do
  status=$(mem0 --agent event status "$event_id" | jq -r '.data.status')
  [ "$status" = "SUCCEEDED" ] || [ "$status" = "FAILED" ] && break
  sleep 2
done
memory_id=$(mem0 --agent event status "$event_id" | jq -r '.data.results[0].id // empty')
if [ -n "$memory_id" ]; then
  echo "Created memory: $memory_id"
fi
```

### Conditional memory addition

```bash
# Only add if search returns no results
count=$(mem0 --agent search "dark mode" --user-id alice 2>/dev/null | jq '.count // 0')
if [ "$count" -eq 0 ]; then
  mem0 add "User prefers dark mode" --user-id alice
fi
```

### Quiet mode for scripts

```bash
# Suppress all output except errors
mem0 add "background note" --user-id alice --output quiet 2>/dev/null
mem0 delete --all --user-id temp-user --force --output quiet 2>/dev/null
```

### Using environment variables for scope

```bash
export MEM0_USER_ID="alice"
export MEM0_API_KEY="m0-xxx"

# All commands now default to user alice, no --user-id needed
mem0 add "prefers dark mode"
mem0 search "preferences"
mem0 list
```

### Timeout handling

The CLI uses a 30-second timeout for normal API requests (the key-validation ping uses 5 seconds and `init` uses 5, 10 and 30 seconds). For long-running scripts, handle timeouts:

```bash
if ! mem0 search "query" --user-id alice -o json 2>/dev/null; then
  echo "Request failed or timed out" >&2
fi
```

---

## Processing Delay Workaround

Memories are processed asynchronously after `mem0 add`. If you need to search for a newly added memory immediately, add a short delay:

```bash
mem0 add "new preference" --user-id alice
sleep 3
mem0 search "new preference" --user-id alice
```

Or use the event system to poll for completion:

```bash
# Add and capture event ID from agent output
result=$(mem0 --agent add "new preference" --user-id alice 2>/dev/null)
event_id=$(echo "$result" | jq -r '.data[0].event_id // empty')

if [ -n "$event_id" ]; then
  # Poll until processing completes
  while true; do
    status=$(mem0 --agent event status "$event_id" 2>/dev/null | jq -r '.data.status')
    if [ "$status" = "SUCCEEDED" ] || [ "$status" = "FAILED" ]; then
      break
    fi
    sleep 1
  done
fi
```

---

## Multi-User Agent Pattern

For AI agents managing memories across multiple users:

```bash
#!/bin/bash
# agent_memory.sh -- manage memories for the current conversation

USER_ID="$1"
ACTION="$2"
shift 2

case "$ACTION" in
  recall)
    mem0 --agent search "$*" --user-id "$USER_ID" 2>/dev/null
    ;;
  remember)
    mem0 --agent add "$*" --user-id "$USER_ID" 2>/dev/null
    ;;
  forget)
    mem0 --agent delete --all --user-id "$USER_ID" --force 2>/dev/null
    ;;
  history)
    mem0 --agent list --user-id "$USER_ID" 2>/dev/null
    ;;
  *)
    echo '{"status":"error","error":"Unknown action: '"$ACTION"'"}' >&2
    exit 1
    ;;
esac
```

Usage:
```bash
./agent_memory.sh alice recall "dietary preferences"
./agent_memory.sh alice remember "allergic to shellfish"
./agent_memory.sh alice history
```
