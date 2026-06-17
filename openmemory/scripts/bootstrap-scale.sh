#!/usr/bin/env bash
#
# Bootstrap idempotente para o stack de escala (ADR-006).
#
# Provisiona PostgreSQL (via compose), roda migrations Alembic, detecta backend
# de inferência local (Ollama / llama.cpp) quando endpoints explícitos não
# estiverem definidos, e aguarda /health antes de liberar o proxy.
#
# Uso:
#   ./scripts/bootstrap-scale.sh
#   ./scripts/bootstrap-scale.sh --skip-detect    # produção com URLs explícitas
#   ./scripts/bootstrap-scale.sh --migrate-sqlite /path/to/openmemory.db
#
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILE="docker-compose.scale.yml"
PROXY_PORT="${PROXY_PORT:-8765}"
TIMEOUT="${TIMEOUT:-300}"
SKIP_DETECT=0
SQLITE_SOURCE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-detect) SKIP_DETECT=1; shift ;;
    --migrate-sqlite) SQLITE_SOURCE="$2"; shift 2 ;;
    --migrate-sqlite=*) SQLITE_SOURCE="${1#*=}"; shift ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *) echo "Argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

echo "==> Subindo infraestrutura base (PostgreSQL, PgBouncer, Redis, Qdrant)..."
docker compose -f "$COMPOSE_FILE" up -d postgres pgbouncer redis mem0_store

echo "==> Aguardando PgBouncer..."
for _ in $(seq 1 60); do
  if docker compose -f "$COMPOSE_FILE" exec -T pgbouncer pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

export DATABASE_URL="postgresql://${POSTGRES_USER:-mem0}:${POSTGRES_PASSWORD:-mem0}@localhost:${PGBOUNCER_PORT:-6432}/${POSTGRES_DB:-openmemory}"

echo "==> Rodando migrations (alembic upgrade head)..."
(
  cd api
  if [ -d .venv ]; then source .venv/bin/activate; fi
  alembic upgrade head
)

if [ -n "$SQLITE_SOURCE" ]; then
  echo "==> Migração guiada SQLite -> PostgreSQL..."
  python3 scripts/migrate_sqlite_to_postgres.py "$SQLITE_SOURCE"
fi

if [ "$SKIP_DETECT" -eq 0 ] && [ -z "${OLLAMA_EMBED_URL:-}" ] && [ -z "${EMBEDDER_BASE_URL:-}" ]; then
  echo "==> Detectando backends locais (Ollama / llama.cpp)..."
  (
    cd api
    python3 - <<'PY'
import json
from app.utils.model_detection import detect_local_models

backends = detect_local_models()
print(json.dumps(backends, indent=2))
if backends.get("ollama", {}).get("available"):
    print("Ollama detectado — configure LLM_MODEL/EMBEDDER_MODEL no .env se necessário.")
elif backends.get("llamacpp", {}).get("available"):
    print("llama.cpp detectado — use provider openai + base_url no .env.")
else:
    print("Nenhum backend local detectado; defina OLLAMA_EMBED_URL / OLLAMA_LLM_URL.")
PY
  )
fi

echo "==> Subindo stack completo..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "==> Aguardando /health via proxy (timeout ${TIMEOUT}s)..."
deadline=$((SECONDS + TIMEOUT))
until curl -sf "http://localhost:${PROXY_PORT}/health" | grep -q '"status"'; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "ERRO: /health não respondeu a tempo." >&2
    exit 1
  fi
  sleep 3
done

echo "==> Stack pronto."
echo "    Proxy MCP:  http://localhost:${PROXY_PORT}/discovery"
echo "    Prometheus: http://localhost:${PROMETHEUS_PORT:-9090}"
echo "    Grafana:    http://localhost:${GRAFANA_PORT:-3001}"
