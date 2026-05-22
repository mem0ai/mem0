#!/usr/bin/env bash
# PreToolUse hook for mcp__mem0__add_memory.
# Injects default metadata fields (confidence, files, source, type) when the
# agent omits them. Reads the tool_input JSON from stdin, patches it, and
# writes the patched version to stdout so the tool call proceeds with complete
# metadata.
#
# Hook contract: exit 0 = allow (stdout replaces tool_input if non-empty).
# exit 2 = block (stdout shown as rejection reason).

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)
case "$TOOL_NAME" in
  mcp__mem0__add_memory|mcp__plugin_mem0_mem0__add_memory) ;;
  *) exit 0 ;;
esac

TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // "{}"' 2>/dev/null)

PATCHED=$(python3 -c "
import json, sys

raw = sys.stdin.read()
try:
    inp = json.loads(raw)
except Exception:
    sys.exit(0)

meta = inp.get('metadata') or {}
changed = False

if 'confidence' not in meta:
    meta['confidence'] = 0.7
    changed = True
if 'files' not in meta:
    meta['files'] = ['*']
    changed = True
if 'source' not in meta:
    meta['source'] = 'auto_capture'
    changed = True
if 'type' not in meta:
    meta['type'] = 'task_learning'
    changed = True

if changed:
    inp['metadata'] = meta
    print(json.dumps(inp))
" <<< "$TOOL_INPUT" 2>/dev/null || true)

if [ -n "$PATCHED" ]; then
  echo "$INPUT" | jq --argjson patched "$PATCHED" '.tool_input = ($patched | tostring)'
fi

exit 0
