#!/usr/bin/env bash
# PreToolUse hook for mcp__mem0__add_memory.
# Injects default metadata fields (confidence, files, source, type) when the
# agent omits them. Uses the hookSpecificOutput.updatedInput contract to
# actually modify the tool call parameters.
#
# Hook contract:
#   exit 0 = allow. If stdout contains {"hookSpecificOutput": {"updatedInput": ...}},
#            the updatedInput replaces the tool's input parameters.
#   exit 2 = block (stderr shown as rejection reason).

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

# If confidence is 1.0 (user explicitly stated), ensure infer=False
if meta.get('confidence', 0) >= 1.0 and 'infer' not in inp:
    inp['infer'] = False
    changed = True

if changed:
    inp['metadata'] = meta
    print(json.dumps(inp))
" <<< "$TOOL_INPUT" 2>/dev/null || true)

if [ -n "$PATCHED" ]; then
  # Use hookSpecificOutput.updatedInput to actually modify the tool call
  jq -n --argjson updated "$PATCHED" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow",
      "updatedInput": $updated
    }
  }'
fi

exit 0
