#!/usr/bin/env bash
# Hook: PreToolUse (matcher: Bash)
#
# Detects `git commit` commands and searches for relevant memories
# about the changed files, surfacing them as pre-commit context.
#
# Input:  JSON on stdin with tool_name, tool_input
# Output: JSON with additionalContext (relevant memories for the commit)

set -uo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  exit 0
fi

case "$COMMAND" in
  *"git commit"*|*"git merge"*|*"git rebase"*)
    ;;
  *)
    exit 0
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

API_KEY="${MEM0_API_KEY:-${CLAUDE_PLUGIN_OPTION_MEM0_API_KEY:-}}"
if [ -z "$API_KEY" ]; then
  exit 0
fi

# Foreground: search for relevant memories about changed files
CHANGED_FILES=$(git diff --cached --name-only 2>/dev/null | head -10 | tr '\n' ', ' | sed 's/,$//')
if [ -z "$CHANGED_FILES" ]; then
  exit 0
fi

USER_ID="${MEM0_RESOLVED_USER_ID:-$USER}"
PROJECT_ID="${MEM0_PROJECT_ID:-unknown}"

CONTEXT=$(python3 -c "
import json, urllib.request, os
api_key = os.environ.get('MEM0_API_KEY', os.environ.get('CLAUDE_PLUGIN_OPTION_MEM0_API_KEY', ''))
user_id = '$USER_ID'
app_id = '$PROJECT_ID'
files = '$CHANGED_FILES'
first_file = files.split(',')[0].strip()
body = json.dumps({
    'query': f'changes to {files}',
    'filters': {'AND': [{'user_id': user_id}, {'app_id': app_id}]},
    'top_k': 3,
}).encode()
req = urllib.request.Request(
    'https://api.mem0.ai/v3/memories/search/',
    data=body,
    headers={'Authorization': f'Token {api_key}', 'Content-Type': 'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        results = json.loads(r.read())
        memories = results if isinstance(results, list) else results.get('results', [])
        if memories:
            lines = ['## Pre-Commit Memory Check', '', 'Relevant memories for files being committed (' + files + '):', '']
            for m in memories[:3]:
                mid = m.get('id', '?')[:8]
                text = m.get('memory', '')[:200]
                cat = (m.get('metadata') or {}).get('type', 'unknown')
                lines.append(f'- [{cat}] {text} [mem0:{mid}]')
            lines.append('')
            lines.append('Consider: does this commit introduce a learning worth saving? If so, suggest storing it after the commit completes.')
            print('\\n'.join(lines))
except Exception:
    pass
" 2>/dev/null || true)

if [ -n "$CONTEXT" ]; then
  jq -nc --arg ctx "$CONTEXT" '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$ctx}}'
fi

exit 0
