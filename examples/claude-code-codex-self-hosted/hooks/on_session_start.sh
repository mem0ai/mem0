#!/usr/bin/env bash
# Hook: SessionStart
#
# Fires when a session starts (or resumes). Recalls memories relevant to the
# current project and user, then injects them as context so the agent starts
# with prior knowledge instead of a blank slate.
#
# Input:  JSON on stdin (session_id, cwd)
# Output: hookSpecificOutput.additionalContext (Claude Code) or plain text (Codex)
#
# Must never block the session: any failure exits 0 silently.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=mem0_env.sh
. "$SCRIPT_DIR/mem0_env.sh" 2>/dev/null || exit 0

if ! mem0_ready; then
  exit 0
fi

INPUT=$(cat)
PROJECT_DIR=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null || echo "")
PROJECT_NAME=$(basename "${PROJECT_DIR:-$(pwd)}")

# Bootstrap queries: pull project context, the user's stated preferences,
# and any recent decisions/learnings from previous sessions.
BOOTSTRAP_QUERY="Project context for ${PROJECT_NAME}: goals, architecture, conventions, and the user's stated preferences."
RESULTS=$(mem0_search "${BOOTSTRAP_QUERY}")
CONTEXT=$(mem0_format_results "${RESULTS}")

if [ -z "$CONTEXT" ]; then
  exit 0
fi

HEADER="Relevant memories from previous sessions (self-hosted Mem0, project: ${PROJECT_NAME}):"
BODY="${HEADER}
${CONTEXT}
Use these memories as context for this session. New learnings will be persisted automatically on session end."

mem0_emit_context "SessionStart" "$BODY"
exit 0
