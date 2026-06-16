#!/usr/bin/env bash
# Smoke test ponta a ponta da Memória Central Compartilhada (task_10).
#
# Sobe o docker-compose, espera a API/MCP e o Qdrant ficarem prontos, valida o
# endpoint de descoberta (task_08) e confere que o Qdrant responde localmente.
# Operação 100% local: nenhuma chamada para fora da rede.
#
# Uso:
#   ./scripts/smoke-memoria-compartilhada.sh           # sobe, valida e derruba
#   KEEP_UP=1 ./scripts/smoke-memoria-compartilhada.sh # sobe e valida, sem derrubar
#
# Variáveis:
#   API_PORT   (default 8765)   porta da API/MCP
#   QDRANT_PORT(default 6333)   porta do Qdrant
#   HOST       (default localhost)
#   TIMEOUT    (default 120)    segundos de espera pelo /discovery

set -euo pipefail

cd "$(dirname "$0")/.."

API_PORT="${API_PORT:-8765}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
HOST="${HOST:-localhost}"
TIMEOUT="${TIMEOUT:-120}"

log() { printf '\n=== %s ===\n' "$*"; }

cleanup() {
  if [ "${KEEP_UP:-0}" != "1" ]; then
    log "derrubando o conjunto"
    docker compose down
  else
    log "KEEP_UP=1: deixando os containers no ar"
  fi
}
trap cleanup EXIT

log "subindo docker-compose (API/MCP + Qdrant)"
docker compose up -d

log "aguardando GET /discovery responder 200 (até ${TIMEOUT}s)"
deadline=$(( SECONDS + TIMEOUT ))
until curl -fsS "http://${HOST}:${API_PORT}/discovery" >/tmp/discovery.json 2>/dev/null; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "ERRO: /discovery não respondeu em ${TIMEOUT}s" >&2
    docker compose logs --tail=50 openmemory-mcp >&2 || true
    exit 1
  fi
  sleep 3
done
echo "OK: /discovery respondeu."

log "validando o conteúdo do /discovery (transport/base_url/route_template/fields)"
for key in transport base_url route_template fields; do
  if ! grep -q "\"${key}\"" /tmp/discovery.json; then
    echo "ERRO: campo '${key}' ausente no /discovery" >&2
    cat /tmp/discovery.json >&2
    exit 1
  fi
done
echo "OK: campos obrigatórios presentes."

log "conferindo o Qdrant (porta ${QDRANT_PORT})"
if ! curl -fsS "http://${HOST}:${QDRANT_PORT}/readyz" >/dev/null 2>&1 \
   && ! curl -fsS "http://${HOST}:${QDRANT_PORT}/" >/dev/null 2>&1; then
  echo "ERRO: Qdrant não respondeu na porta ${QDRANT_PORT}" >&2
  exit 1
fi
echo "OK: Qdrant respondendo."

log "SMOKE OK — conjunto local-first no ar (API/MCP + Qdrant + descoberta)"
