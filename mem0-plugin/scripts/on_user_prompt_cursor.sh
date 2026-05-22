#!/usr/bin/env bash
# Hook: beforeSubmitPrompt (Cursor)
#
# Wraps on_user_prompt.sh and converts plain-text output to Cursor's
# expected JSON format: {"continue":true,"user_message":"<text>"}

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

TEXT=$("$SCRIPT_DIR/on_user_prompt.sh" 2>/dev/null || echo "")

if [ -z "$TEXT" ]; then
  jq -cn '{continue:true}'
  exit 0
fi

jq -cn --arg msg "$TEXT" '{continue:true, user_message:$msg}'
exit 0
