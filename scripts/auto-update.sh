#!/usr/bin/env bash
set -euo pipefail

REPO="/home/luka/projects/mem0"
LOG="/home/luka/logs/mem0-update.log"
cd "$REPO"

echo "=== mem0 auto-update $(date -Iseconds) ==="

# Fetch and check for upstream changes before doing anything
git fetch origin main --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [[ "$LOCAL" == "$REMOTE" ]] || git merge-base --is-ancestor "$REMOTE" HEAD 2>/dev/null; then
    echo "Already up to date (local: ${LOCAL:0:8}, remote: ${REMOTE:0:8})"
    exit 0
fi

echo "Upstream has new commits: ${LOCAL:0:8} -> ${REMOTE:0:8}"
echo "Handing off to Claude..."

claude -p "
You are maintaining a private fork of mem0 at $REPO. Upstream (origin/main) has new commits.

Current state:
- Local HEAD: $LOCAL
- Remote HEAD: $REMOTE
- There may be uncommitted local changes (patches to .env, docker-compose.yml, mcp_server.py, configs, etc.)
- There may be local commits not in upstream

Your job:
1. Stash any uncommitted changes
2. Integrate upstream changes (prefer rebase to keep local commits on top, fall back to merge if rebase conflicts are complex)
3. If there are conflicts, resolve them intelligently — our local changes to openmemory/api/.env, docker-compose.yml, and app/mcp_server.py are intentional single-user patches that should be preserved
4. Pop the stash, resolve any stash conflicts similarly
5. Check if openmemory/api/requirements.txt changed in the upstream diff — if yes, rebuild: cd openmemory && docker compose up -d --build openmemory-mcp
6. If requirements.txt didn't change, just restart: cd openmemory && docker compose restart openmemory-mcp
7. Verify the API is healthy: curl -sf http://localhost:8765/docs
8. Print a concise summary of what changed

If anything goes wrong that you can't fix, abort cleanly (git rebase --abort / git stash pop) and report the error. Do not force-push or destroy any local state.
" 2>&1

echo "=== Done $(date -Iseconds) ==="
