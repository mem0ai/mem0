#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OPENAPI_FILE="${OPENAPI_FILE:-$HOME/.openapi}"
OPENAPI_ENV_FILE=".openapi.env"

if [[ ! -f "$OPENAPI_FILE" ]]; then
  cat >&2 <<EOF
Missing $OPENAPI_FILE.
Create it as an env file with at least:
  OPENAI_API_KEY=<internal-token>
  OPENAI_BASE_URL=https://<internal-openai-compatible-api>/v1
  MEM0_DEFAULT_LLM_MODEL=<chat-model-name>
EOF
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  python3 - <<'PY'
from pathlib import Path
import secrets

p = Path(".env")
text = p.read_text()
replacements = {
    "POSTGRES_PASSWORD=": f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}",
    "JWT_SECRET=": f"JWT_SECRET={secrets.token_urlsafe(48)}",
    "ADMIN_PASSWORD=": f"ADMIN_PASSWORD={secrets.token_urlsafe(18)}",
}
for needle, value in replacements.items():
    text = text.replace(needle, value, 1)
p.write_text(text)
PY
  chmod 600 .env
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

if grep -qE '^[A-Za-z_][A-Za-z0-9_]*=' "$OPENAPI_FILE"; then
  set -a
  # shellcheck disable=SC1090
  . "$OPENAPI_FILE"
  set +a
else
  OPENAI_API_KEY="$(tr -d '[:space:]' < "$OPENAPI_FILE")"
  export OPENAI_API_KEY
fi

OPENAI_BASE_URL="${OPENAI_BASE_URL:-}"
MEM0_DEFAULT_LLM_MODEL="${MEM0_DEFAULT_LLM_MODEL:-}"

: "${OPENAI_API_KEY:?OPENAI_API_KEY is required in $OPENAPI_FILE}"
: "${OPENAI_BASE_URL:?OPENAI_BASE_URL is required in .env or $OPENAPI_FILE}"
: "${MEM0_DEFAULT_LLM_MODEL:?MEM0_DEFAULT_LLM_MODEL is required in .env or $OPENAPI_FILE}"

python3 - <<'PY'
from pathlib import Path
import os

def env_line(key: str) -> str:
    value = os.environ[key]
    escaped = value.replace("\\", "\\\\").replace("\n", "")
    return f"{key}={escaped}\n"

Path(".openapi.env").write_text(
    env_line("OPENAI_API_KEY")
    + env_line("OPENAI_BASE_URL")
    + env_line("MEM0_DEFAULT_LLM_MODEL")
)
PY
chmod 600 "$OPENAPI_ENV_FILE"

API_URL="http://localhost:${API_PORT:-8888}"
DASHBOARD_URL="http://localhost:${DASHBOARD_PORT:-3000}"

docker compose up -d --build

echo "Waiting for Mem0 API at $API_URL..."
until curl -fsS "$API_URL/auth/setup-status" >/dev/null 2>&1; do
  sleep 2
done

echo "Waiting for dashboard at $DASHBOARD_URL..."
until curl -fsS "$DASHBOARD_URL/api/health" >/dev/null 2>&1; do
  sleep 2
done

SETUP="$(curl -fsS "$API_URL/auth/setup-status")"
NEEDS_SETUP="$(printf '%s' "$SETUP" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("needsSetup", True))')"

if [[ "$NEEDS_SETUP" == "True" ]]; then
  echo "Creating admin account..."
  REGISTER_PAYLOAD="$(
    ADMIN_NAME="$ADMIN_NAME" ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" python3 - <<'PY'
import json
import os
print(json.dumps({
    "name": os.environ["ADMIN_NAME"],
    "email": os.environ["ADMIN_EMAIL"],
    "password": os.environ["ADMIN_PASSWORD"],
}))
PY
  )"
  curl -fsS -X POST "$API_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "$REGISTER_PAYLOAD" >/dev/null
fi

LOGIN_PAYLOAD="$(
  ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" python3 - <<'PY'
import json
import os
print(json.dumps({
    "email": os.environ["ADMIN_EMAIL"],
    "password": os.environ["ADMIN_PASSWORD"],
}))
PY
)"
TOKEN="$(
  curl -fsS -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "$LOGIN_PAYLOAD" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
)"

KEY_RESP="$(
  curl -fsS -X POST "$API_URL/api-keys" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"label":"closed-network-bootstrap"}'
)"
API_KEY="$(printf '%s' "$KEY_RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["key"])')"
printf '%s\n' "$API_KEY" > .mem0-api-key
chmod 600 .mem0-api-key

CONFIG_PAYLOAD="$(
  python3 - <<'PY'
import json
import os

payload = {
    "version": "v1.1",
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "embedding_model_dims": int(os.environ.get("MEM0_DEFAULT_EMBEDDER_DIMS", "768")),
        },
    },
    "llm": {
        "provider": "openai",
        "config": {
            "api_key": os.environ["OPENAI_API_KEY"],
            "openai_base_url": os.environ["OPENAI_BASE_URL"],
            "model": os.environ["MEM0_DEFAULT_LLM_MODEL"],
            "temperature": float(os.environ.get("MEM0_DEFAULT_LLM_TEMPERATURE", "0.2")),
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
            "ollama_base_url": "http://ollama:11434",
            "embedding_dims": int(os.environ.get("MEM0_DEFAULT_EMBEDDER_DIMS", "768")),
        },
    },
}
print(json.dumps(payload))
PY
)"

curl -fsS -X POST "$API_URL/configure" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "$CONFIG_PAYLOAD" >/dev/null

cat <<EOF
Mem0 closed-network stack is ready.
  API:       $API_URL
  Dashboard: $DASHBOARD_URL
  Admin:     $ADMIN_EMAIL
  API key:   $ROOT/.mem0-api-key

Run ./scripts/smoke-test.sh to add and search a test memory.
EOF
