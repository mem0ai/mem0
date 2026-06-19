#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env. Run ./scripts/bootstrap.sh first." >&2
  exit 1
fi
if [[ ! -f .mem0-api-key ]]; then
  echo "Missing .mem0-api-key. Run ./scripts/bootstrap.sh first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

API_URL="http://localhost:${API_PORT:-8888}"
API_KEY="$(cat .mem0-api-key)"
USER_ID="${MEM0_SMOKE_USER_ID:-closed-network-smoke}"

echo "Adding a memory..."
ADD_RESPONSE="$(
  curl -fsS -X POST "$API_URL/memories" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"messages\": [
      {\"role\": \"user\", \"content\": \"I use self-hosted Mem0 with a local embedding model.\"}
    ],
    \"user_id\": \"$USER_ID\"
  }"
)"

ADD_RESPONSE="$ADD_RESPONSE" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["ADD_RESPONSE"])
if not payload.get("results"):
    raise SystemExit(f"Add returned no memories: {payload}")
PY

echo "Searching memories..."
SEARCH_RESPONSE="$(
  curl -fsS -X POST "$API_URL/search" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"local embedding model\",
    \"filters\": {\"user_id\": \"$USER_ID\"},
    \"top_k\": 3,
    \"threshold\": 0
  }"
)"

SEARCH_RESPONSE="$SEARCH_RESPONSE" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["SEARCH_RESPONSE"])
if not payload.get("results"):
    raise SystemExit(f"Search returned no memories: {payload}")
print(json.dumps(payload, indent=2))
PY
