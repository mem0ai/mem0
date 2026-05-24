#!/usr/bin/env bash
# Hook: PreToolUse (matcher: Read)
#
# When Claude reads a file, searches mem0 for memories tagged with that
# file path. Injects results as additionalContext if found.

set -uo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Skip non-code files (images, binaries, lockfiles, etc.)
case "$FILE_PATH" in
  *.png|*.jpg|*.jpeg|*.gif|*.svg|*.ico|*.woff|*.woff2|*.ttf|*.eot) exit 0 ;;
  *.lock|*.sum|*.min.js|*.min.css|*.map) exit 0 ;;
  *node_modules/*|*.git/*|*__pycache__/*) exit 0 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

# Skip if no API key (checked after _identity.sh resolves CLAUDE_PLUGIN_OPTION_MEM0_API_KEY)
if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

# Skip repeated reads: track last 10 files in a temp file.
# Use full FILE_PATH (not basename) to avoid false dedup.
RECENT_FILE="/tmp/mem0_recent_reads_${USER}_${MEM0_PROJECT_ID:-unknown}"
if [ -f "$RECENT_FILE" ] && grep -qxF "$FILE_PATH" "$RECENT_FILE" 2>/dev/null; then
  exit 0
fi
echo "$FILE_PATH" >> "$RECENT_FILE" 2>/dev/null || true
tail -10 "$RECENT_FILE" > "$RECENT_FILE.tmp" 2>/dev/null && mv "$RECENT_FILE.tmp" "$RECENT_FILE" 2>/dev/null || true

USER_ID="${MEM0_RESOLVED_USER_ID:-${USER:-default}}"
PROJECT_ID="${MEM0_PROJECT_ID:-unknown}"
BASENAME=$(basename "$FILE_PATH")

CWD="${MEM0_CWD:-$(pwd)}"
REL_PATH="${FILE_PATH#$CWD/}"
if [ "$REL_PATH" = "$FILE_PATH" ]; then
  REL_PATH="$BASENAME"
fi

CONTEXT=$(PYTHONPATH="$SCRIPT_DIR" MEM0_SEARCH_USER="$USER_ID" MEM0_SEARCH_PROJECT="$PROJECT_ID" MEM0_SEARCH_QUERY="$BASENAME" MEM0_SEARCH_RELPATH="$REL_PATH" python3 -c "
import os, sys
sys.path.insert(0, os.environ.get('PYTHONPATH', '.'))
from _search import search_memories, format_results_for_context

api_key = os.environ.get('MEM0_API_KEY', '')
user_id = os.environ.get('MEM0_SEARCH_USER', 'default')
project_id = os.environ.get('MEM0_SEARCH_PROJECT', 'unknown')
filename = os.environ.get('MEM0_SEARCH_QUERY', '')
relpath = os.environ.get('MEM0_SEARCH_RELPATH', '')

results = search_memories(
    api_key, user_id, project_id, filename,
    metadata_filters={'files': {'contains': relpath}} if relpath else None,
    top_k=3, min_score=0.4,
)
if not results and relpath:
    results = search_memories(
        api_key, user_id, project_id, filename,
        top_k=3, min_score=0.4,
    )
if results:
    print(format_results_for_context(results, heading=f'mem0 context for {filename}'))
" 2>/dev/null || true)

if [ -n "$CONTEXT" ]; then
  jq -nc --arg ctx "$CONTEXT" '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$ctx}}'
fi

exit 0
