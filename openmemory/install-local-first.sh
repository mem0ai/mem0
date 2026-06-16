#!/usr/bin/env bash
#
# Instalação rápida LOCAL-FIRST da Memória Central Compartilhada (Linux).
#
# Sobe API/MCP + Qdrant em container e usa um Ollama LOCAL para LLM/embeddings.
# Operação 100% local: nenhuma dependência de serviços fora da rede (privacidade).
#
# O que faz, ponta a ponta:
#   1. Verifica pré-requisitos (Docker + Docker Compose v2).
#   2. Garante os arquivos .env (compose + api).
#   3. Detecta os modelos do Ollama (GET /api/tags) e deixa você escolher o LLM
#      e o embedder — sem digitar nomes na mão, sem download automático (task_09).
#   4. Persiste a seleção no .env do compose (interpolado no docker-compose.yml).
#   5. Sobe o conjunto (docker compose up -d) — o schema é criado no startup.
#   6. Valida a auto-descoberta (GET /discovery) e imprime os dados de conexão.
#
# Uso:
#   ./install-local-first.sh                          # interativo
#   ./install-local-first.sh --ollama-url http://192.168.0.10:11434
#   ./install-local-first.sh --llm llama3.1:latest --embedder nomic-embed-text --yes
#   ./install-local-first.sh --skip-models            # mantém modelos do .env atual
#   ./install-local-first.sh --with-ui                # também sobe a UI (porta 3000)
#
# Variáveis (alternativa às flags):
#   OLLAMA_URL   endpoint do Ollama p/ detecção no host (default http://localhost:11434)
#   API_PORT     porta da API/MCP (default 8765)
#   TIMEOUT      segundos de espera pelo /discovery (default 180)

set -euo pipefail

# Sempre operar a partir do diretório do compose (onde este script vive).
cd "$(dirname "$0")"

# --------------------------------------------------------------------------- #
# Parâmetros
# --------------------------------------------------------------------------- #
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
API_PORT="${API_PORT:-8765}"
TIMEOUT="${TIMEOUT:-180}"
LLM_CHOICE=""
EMBEDDER_CHOICE=""
NON_INTERACTIVE=0
SKIP_MODELS=0
WITH_UI=0
OLLAMA_URL_EXPLICIT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --ollama-url) OLLAMA_URL="$2"; OLLAMA_URL_EXPLICIT=1; shift 2 ;;
    --ollama-url=*) OLLAMA_URL="${1#*=}"; OLLAMA_URL_EXPLICIT=1; shift ;;
    --llm) LLM_CHOICE="$2"; shift 2 ;;
    --llm=*) LLM_CHOICE="${1#*=}"; shift ;;
    --embedder) EMBEDDER_CHOICE="$2"; shift 2 ;;
    --embedder=*) EMBEDDER_CHOICE="${1#*=}"; shift ;;
    --yes|-y) NON_INTERACTIVE=1; shift ;;
    --skip-models) SKIP_MODELS=1; shift ;;
    --with-ui) WITH_UI=1; shift ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "Argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

log()  { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  ! \033[0m%s\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

# --------------------------------------------------------------------------- #
# 1. Pré-requisitos
# --------------------------------------------------------------------------- #
log "Verificando pré-requisitos"
command -v docker >/dev/null 2>&1 || die "Docker não encontrado. Instale o Docker."
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 não encontrado (use 'docker compose')."
command -v curl >/dev/null 2>&1 || die "curl não encontrado. Instale o curl."
ok "Docker, Docker Compose v2 e curl disponíveis."

# --------------------------------------------------------------------------- #
# 2. Arquivos .env
# --------------------------------------------------------------------------- #
COMPOSE_ENV=".env"          # lido pela interpolação ${VAR} do docker-compose.yml
API_ENV="api/.env"          # injetado no container via env_file

log "Preparando arquivos de ambiente"
[ -f "api/.env.example" ] || die "api/.env.example não encontrado (rode a partir de openmemory/)."
if [ ! -f "$API_ENV" ]; then
  cp "api/.env.example" "$API_ENV"
  ok "Criado $API_ENV a partir do exemplo."
else
  ok "$API_ENV já existe (preservado)."
fi
touch "$COMPOSE_ENV"

# Escreve/atualiza KEY=VALUE em um arquivo .env de forma idempotente (GNU tools).
set_env() {
  local key="$1" val="$2" file="$3" tmp
  tmp="$(mktemp)"
  if grep -qE "^[#[:space:]]*${key}=" "$file" 2>/dev/null; then
    awk -v k="$key" -v v="$val" '
      $0 ~ "^[#[:space:]]*" k "=" { print k "=" v; next } { print }
    ' "$file" > "$tmp" && mv "$tmp" "$file"
  else
    cp "$file" "$tmp" && printf '%s=%s\n' "$key" "$val" >> "$tmp" && mv "$tmp" "$file"
  fi
}

# --------------------------------------------------------------------------- #
# 3. Detecção de modelos (Ollama /api/tags) — task_09
# --------------------------------------------------------------------------- #
# Extrai os nomes de modelo do JSON do /api/tags (python3 se houver; senão grep).
parse_models() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import sys,json
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
for m in d.get("models",[]):
    n=(m.get("name") or m.get("model"));
    print(n) if n else None'
  else
    grep -oE '"(name|model)"[[:space:]]*:[[:space:]]*"[^"]+"' \
      | sed -E 's/.*:[[:space:]]*"([^"]+)"/\1/'
  fi
}

select_model() {  # $1 = rótulo (LLM/embedder); usa a global MODELS; ecoa a escolha
  local role="$1" choice
  read -r -p "  Selecione o modelo de ${role} (número ou nome): " choice </dev/tty
  if printf '%s' "$choice" | grep -qE '^[0-9]+$'; then
    printf '%s\n' "$MODELS" | sed -n "${choice}p"
  else
    printf '%s\n' "$choice"
  fi
}

if [ "$SKIP_MODELS" -eq 1 ]; then
  log "Detecção de modelos pulada (--skip-models): mantendo o .env atual."
else
  log "Detectando modelos no Ollama em $OLLAMA_URL"
  TAGS_JSON="$(curl -fsS "${OLLAMA_URL%/}/api/tags" 2>/dev/null || true)"
  MODELS="$(printf '%s' "$TAGS_JSON" | parse_models)"

  if [ -n "${LLM_CHOICE}" ] && [ -n "${EMBEDDER_CHOICE}" ]; then
    ok "Usando modelos informados por flag."
  elif [ "$NON_INTERACTIVE" -eq 1 ]; then
    die "--yes exige --llm e --embedder."
  elif [ -n "$MODELS" ]; then
    ok "Modelos detectados:"
    printf '%s\n' "$MODELS" | nl -w4 -s'. ' | sed 's/^/   /'
    LLM_CHOICE="$(select_model "LLM")"
    EMBEDDER_CHOICE="$(select_model "embedder")"
  else
    warn "Ollama indisponível ou sem modelos em $OLLAMA_URL — entrada manual."
    read -r -p "  Nome do modelo LLM: " LLM_CHOICE </dev/tty
    read -r -p "  Nome do modelo embedder: " EMBEDDER_CHOICE </dev/tty
  fi

  [ -n "$LLM_CHOICE" ] || die "Modelo LLM não definido."
  [ -n "$EMBEDDER_CHOICE" ] || die "Modelo embedder não definido."

  # 4. Persiste a seleção no .env do compose (interpolado em docker-compose.yml).
  log "Gravando a seleção em $COMPOSE_ENV"
  set_env "LLM_PROVIDER" "ollama" "$COMPOSE_ENV"
  set_env "EMBEDDER_PROVIDER" "ollama" "$COMPOSE_ENV"
  set_env "LLM_MODEL" "$LLM_CHOICE" "$COMPOSE_ENV"
  set_env "EMBEDDER_MODEL" "$EMBEDDER_CHOICE" "$COMPOSE_ENV"
  # Só fixa OLLAMA_BASE_URL para o container quando o usuário deu uma URL de rede;
  # caso contrário mantém o default host.docker.internal do compose.
  if [ "$OLLAMA_URL_EXPLICIT" -eq 1 ]; then
    set_env "OLLAMA_BASE_URL" "$OLLAMA_URL" "$COMPOSE_ENV"
  fi
  ok "LLM=$LLM_CHOICE | embedder=$EMBEDDER_CHOICE"
fi

# USER/NEXT_PUBLIC_API_URL ajudam a UI e silenciam avisos do compose.
set_env "USER" "${USER:-openmemory}" "$COMPOSE_ENV"
set_env "NEXT_PUBLIC_API_URL" "http://localhost:${API_PORT}" "$COMPOSE_ENV"

# --------------------------------------------------------------------------- #
# 5. Subir o conjunto (schema criado no startup via create_all)
# --------------------------------------------------------------------------- #
SERVICES="mem0_store openmemory-mcp"
[ "$WITH_UI" -eq 1 ] && SERVICES="$SERVICES openmemory-ui"
log "Subindo containers: $SERVICES"
docker compose up -d --build $SERVICES

# --------------------------------------------------------------------------- #
# 6. Validar a auto-descoberta (task_08)
# --------------------------------------------------------------------------- #
log "Aguardando GET /discovery (até ${TIMEOUT}s)"
deadline=$(( SECONDS + TIMEOUT ))
until curl -fsS "http://localhost:${API_PORT}/discovery" >/tmp/om_discovery.json 2>/dev/null; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    docker compose logs --tail=40 openmemory-mcp >&2 || true
    die "/discovery não respondeu em ${TIMEOUT}s."
  fi
  sleep 3
done
for key in transport base_url route_template fields; do
  grep -q "\"${key}\"" /tmp/om_discovery.json || die "campo '${key}' ausente em /discovery."
done
ok "/discovery respondeu 200 com os campos esperados."

# --------------------------------------------------------------------------- #
# Pronto
# --------------------------------------------------------------------------- #
log "Instalação local-first concluída 🎉"
cat <<EOF

  API/MCP:    http://localhost:${API_PORT}
  Descoberta: http://localhost:${API_PORT}/discovery
  Qdrant:     http://localhost:6333
$( [ "$WITH_UI" -eq 1 ] && echo "  UI:         http://localhost:3000" )

  Rota MCP (preencha hostname e project):
    /mcp/{client_name}/sse/{hostname}      (SSE)
    /mcp/{client_name}/http/{hostname}     (Streamable HTTP)

  Os agentes na rede local podem se autoconfigurar via GET /discovery.
  Smoke completo (opcional):  ./scripts/smoke-memoria-compartilhada.sh
EOF
