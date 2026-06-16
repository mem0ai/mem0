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
#   3. Detecta modelos locais — Ollama (GET /api/tags) E llama.cpp (servidor
#      OpenAI-compatível, GET /v1/models) — e deixa você escolher o backend e os
#      modelos LLM/embedder, sem download automático (task_09).
#   4. Persiste a seleção no .env do compose (interpolado no docker-compose.yml).
#   5. Sobe o conjunto (docker compose up -d) — o schema é criado no startup.
#   6. Valida a auto-descoberta (GET /discovery) e imprime os dados de conexão.
#
# Uso:
#   ./install-local-first.sh                          # interativo (auto-detecta)
#   ./install-local-first.sh --backend llamacpp       # força o backend llama.cpp
#   ./install-local-first.sh --ollama-url http://192.168.0.10:11434
#   ./install-local-first.sh --llamacpp-url http://192.168.0.10:8080
#   ./install-local-first.sh --llm llama3.1:latest --embedder nomic-embed-text --yes
#   ./install-local-first.sh --api-key SEU_TOKEN      # token do backend local (opcional)
#   ./install-local-first.sh --data-dir /srv/mem0-data  # salva Qdrant + SQLite nesse caminho
#   ./install-local-first.sh --skip-models            # mantém modelos do .env atual
#   ./install-local-first.sh --with-ui                # também sobe a UI (porta 3000)
#
# Variáveis (alternativa às flags):
#   OLLAMA_URL    endpoint do Ollama p/ detecção no host (default http://localhost:11434)
#   LLAMACPP_URL  endpoint do llama.cpp p/ detecção no host (default http://localhost:8080)
#   API_PORT      porta da API/MCP (default 8765)
#   TIMEOUT       segundos de espera pelo /discovery (default 180)

set -euo pipefail

# Sempre operar a partir do diretório do compose (onde este script vive).
cd "$(dirname "$0")"

# --------------------------------------------------------------------------- #
# Parâmetros
# --------------------------------------------------------------------------- #
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
LLAMACPP_URL="${LLAMACPP_URL:-http://localhost:8080}"
BACKEND="auto"
API_PORT="${API_PORT:-8765}"
TIMEOUT="${TIMEOUT:-180}"
LLM_CHOICE=""
EMBEDDER_CHOICE=""
API_KEY_CHOICE=""
API_KEY_SET=0
DATA_DIR=""
NON_INTERACTIVE=0
SKIP_MODELS=0
WITH_UI=0
OLLAMA_URL_EXPLICIT=0
LLAMACPP_URL_EXPLICIT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --backend) BACKEND="$2"; shift 2 ;;
    --backend=*) BACKEND="${1#*=}"; shift ;;
    --ollama-url) OLLAMA_URL="$2"; OLLAMA_URL_EXPLICIT=1; shift 2 ;;
    --ollama-url=*) OLLAMA_URL="${1#*=}"; OLLAMA_URL_EXPLICIT=1; shift ;;
    --llamacpp-url) LLAMACPP_URL="$2"; LLAMACPP_URL_EXPLICIT=1; shift 2 ;;
    --llamacpp-url=*) LLAMACPP_URL="${1#*=}"; LLAMACPP_URL_EXPLICIT=1; shift ;;
    --llm) LLM_CHOICE="$2"; shift 2 ;;
    --llm=*) LLM_CHOICE="${1#*=}"; shift ;;
    --embedder) EMBEDDER_CHOICE="$2"; shift 2 ;;
    --embedder=*) EMBEDDER_CHOICE="${1#*=}"; shift ;;
    --api-key) API_KEY_CHOICE="$2"; API_KEY_SET=1; shift 2 ;;
    --api-key=*) API_KEY_CHOICE="${1#*=}"; API_KEY_SET=1; shift ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --data-dir=*) DATA_DIR="${1#*=}"; shift ;;
    --yes|-y) NON_INTERACTIVE=1; shift ;;
    --skip-models) SKIP_MODELS=1; shift ;;
    --with-ui) WITH_UI=1; shift ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    *) echo "Argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

case "$BACKEND" in auto|ollama|llamacpp) ;; *) echo "--backend invalido: $BACKEND" >&2; exit 2 ;; esac

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
# 3. Detecção de modelos (Ollama /api/tags + llama.cpp /v1/models) — task_09
# --------------------------------------------------------------------------- #
# Extrai nomes de modelo de um JSON (python3 se houver; senão grep). $1 = chave da
# lista ("models" p/ Ollama, "data" p/ llama.cpp).
parse_models() {
  local list_key="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import sys,json
key=sys.argv[1]
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
for m in d.get(key,[]) or []:
    n=(m.get("name") or m.get("model") or m.get("id"))
    print(n) if n else None' "$list_key"
  else
    grep -oE '"(name|model|id)"[[:space:]]*:[[:space:]]*"[^"]+"' \
      | sed -E 's/.*:[[:space:]]*"([^"]+)"/\1/'
  fi
}

select_from() {  # $1 = rótulo; $2 = lista (newline-separated); ecoa a escolha
  local role="$1" list="$2" choice
  read -r -p "  Selecione o ${role} (número ou nome): " choice </dev/tty
  if printf '%s' "$choice" | grep -qE '^[0-9]+$'; then
    printf '%s\n' "$list" | sed -n "${choice}p"
  else
    printf '%s\n' "$choice"
  fi
}

if [ "$SKIP_MODELS" -eq 1 ]; then
  log "Detecção de modelos pulada (--skip-models): mantendo o .env atual."
else
  log "Detectando modelos locais (Ollama + llama.cpp)"
  OLLAMA_MODELS=""; LLAMACPP_MODELS=""
  if [ "$BACKEND" = "auto" ] || [ "$BACKEND" = "ollama" ]; then
    OLLAMA_MODELS="$(curl -fsS "${OLLAMA_URL%/}/api/tags" 2>/dev/null | parse_models models || true)"
  fi
  if [ "$BACKEND" = "auto" ] || [ "$BACKEND" = "llamacpp" ]; then
    LC_BASE="${LLAMACPP_URL%/}"; case "$LC_BASE" in */v1) ;; *) LC_BASE="$LC_BASE/v1" ;; esac
    LLAMACPP_MODELS="$(curl -fsS "${LC_BASE}/models" 2>/dev/null | parse_models data || true)"
  fi

  BACKEND_CHOSEN=""; MODELS=""
  if [ -n "${LLM_CHOICE}" ] && [ -n "${EMBEDDER_CHOICE}" ]; then
    [ "$BACKEND" = "llamacpp" ] && BACKEND_CHOSEN="llamacpp" || BACKEND_CHOSEN="ollama"
    ok "Usando modelos informados por flag (backend $BACKEND_CHOSEN)."
  elif [ "$NON_INTERACTIVE" -eq 1 ]; then
    die "--yes exige --llm e --embedder."
  else
    # Quais backends têm modelos?
    avail=""
    [ -n "$OLLAMA_MODELS" ] && avail="$avail ollama"
    [ -n "$LLAMACPP_MODELS" ] && avail="$avail llamacpp"
    avail="$(printf '%s' "$avail" | xargs 2>/dev/null || echo "$avail")"
    n_avail=$(printf '%s\n' $avail | grep -c . || true)

    if [ "$n_avail" -gt 1 ]; then
      ok "Múltiplos backends locais detectados:"
      i=1; for b in $avail; do printf '   %d. %s\n' "$i" "$b"; i=$((i+1)); done
      pick="$(select_from "backend" "$(printf '%s\n' $avail)")"
      BACKEND_CHOSEN="$pick"
    elif [ "$n_avail" -eq 1 ]; then
      BACKEND_CHOSEN="$(printf '%s' "$avail" | xargs)"
    fi

    if [ -n "$BACKEND_CHOSEN" ]; then
      [ "$BACKEND_CHOSEN" = "llamacpp" ] && MODELS="$LLAMACPP_MODELS" || MODELS="$OLLAMA_MODELS"
      ok "Backend $BACKEND_CHOSEN — modelos detectados:"
      printf '%s\n' "$MODELS" | nl -w4 -s'. ' | sed 's/^/   /'
      LLM_CHOICE="$(select_from "modelo LLM" "$MODELS")"
      EMBEDDER_CHOICE="$(select_from "modelo embedder" "$MODELS")"
    else
      warn "Nenhum backend local detectou modelos — entrada manual."
      [ "$BACKEND" = "llamacpp" ] && BACKEND_CHOSEN="llamacpp" || BACKEND_CHOSEN="ollama"
      read -r -p "  Nome do modelo LLM: " LLM_CHOICE </dev/tty
      read -r -p "  Nome do modelo embedder: " EMBEDDER_CHOICE </dev/tty
    fi
  fi

  [ -n "$LLM_CHOICE" ] || die "Modelo LLM não definido."
  [ -n "$EMBEDDER_CHOICE" ] || die "Modelo embedder não definido."

  # Token/API key do backend local detectado (opcional — Ollama não exige; Enter
  # deixa em branco). Aplica-se ao LLM e ao embedder.
  if [ "$API_KEY_SET" -ne 1 ] && [ "$NON_INTERACTIVE" -ne 1 ]; then
    read -r -p "  Token/API key do ${BACKEND_CHOSEN} (Enter se não houver): " API_KEY_CHOICE </dev/tty
  fi

  # 4. Persiste a seleção no .env do compose (interpolado em docker-compose.yml).
  log "Gravando a seleção em $COMPOSE_ENV"
  set_env "LLM_MODEL" "$LLM_CHOICE" "$COMPOSE_ENV"
  set_env "EMBEDDER_MODEL" "$EMBEDDER_CHOICE" "$COMPOSE_ENV"
  if [ "$BACKEND_CHOSEN" = "llamacpp" ]; then
    # llama.cpp via provider openai apontando para o servidor local. localhost
    # não serve de dentro do container: usa a URL informada ou host.docker.internal.
    if [ "$LLAMACPP_URL_EXPLICIT" -eq 1 ]; then LC_CONT="${LLAMACPP_URL%/}"; else LC_CONT="http://host.docker.internal:8080"; fi
    case "$LC_CONT" in */v1) ;; *) LC_CONT="$LC_CONT/v1" ;; esac
    # O provider openai exige key não-vazia: usa a informada ou placeholder.
    LC_KEY="${API_KEY_CHOICE:-llama.cpp}"
    set_env "LLM_PROVIDER" "openai" "$COMPOSE_ENV"
    set_env "EMBEDDER_PROVIDER" "openai" "$COMPOSE_ENV"
    set_env "LLM_BASE_URL" "$LC_CONT" "$COMPOSE_ENV"
    set_env "EMBEDDER_BASE_URL" "$LC_CONT" "$COMPOSE_ENV"
    set_env "LLM_API_KEY" "$LC_KEY" "$COMPOSE_ENV"
    set_env "EMBEDDER_API_KEY" "$LC_KEY" "$COMPOSE_ENV"
  else
    set_env "LLM_PROVIDER" "ollama" "$COMPOSE_ENV"
    set_env "EMBEDDER_PROVIDER" "ollama" "$COMPOSE_ENV"
    # Token opcional do Ollama (em branco quando não informado).
    set_env "LLM_API_KEY" "$API_KEY_CHOICE" "$COMPOSE_ENV"
    set_env "EMBEDDER_API_KEY" "$API_KEY_CHOICE" "$COMPOSE_ENV"
    # Só fixa OLLAMA_BASE_URL quando o usuário deu uma URL de rede; senão mantém
    # o default host.docker.internal do compose.
    if [ "$OLLAMA_URL_EXPLICIT" -eq 1 ]; then
      set_env "OLLAMA_BASE_URL" "$OLLAMA_URL" "$COMPOSE_ENV"
    fi
  fi
  [ -n "$API_KEY_CHOICE" ] && KEY_NOTE="com token" || KEY_NOTE="sem token"
  ok "Backend=$BACKEND_CHOSEN | LLM=$LLM_CHOICE | embedder=$EMBEDDER_CHOICE | $KEY_NOTE"
fi

# USER/NEXT_PUBLIC_API_URL ajudam a UI e silenciam avisos do compose.
set_env "USER" "${USER:-openmemory}" "$COMPOSE_ENV"
set_env "NEXT_PUBLIC_API_URL" "http://localhost:${API_PORT}" "$COMPOSE_ENV"

# --------------------------------------------------------------------------- #
# 4b. Local de salvamento das memórias (Qdrant + SQLite) — task_11
# --------------------------------------------------------------------------- #
# Sem caminho: volumes Docker gerenciados (padrão). Interativo sempre pergunta;
# Enter mantém o padrão. Um caminho reloca AMBOS os stores sob <dir>/qdrant e
# <dir>/db, repontando DATABASE_URL para /data/openmemory.db.
log "Definindo o local de salvamento das memórias"
if [ -z "$DATA_DIR" ] && [ "$NON_INTERACTIVE" -ne 1 ]; then
  printf '  Onde salvar as memórias (Qdrant + SQLite)?\n'
  read -r -p "  [Enter] = volumes Docker gerenciados (padrão) | ou informe um caminho: " DATA_DIR </dev/tty
fi
if [ -z "$DATA_DIR" ]; then
  set_env "QDRANT_STORAGE" "mem0_storage" "$COMPOSE_ENV"
  set_env "SQLITE_STORAGE" "mem0_db" "$COMPOSE_ENV"
  set_env "DATABASE_URL" "sqlite:////usr/src/openmemory/openmemory.db" "$COMPOSE_ENV"
  ok "Armazenamento: volumes Docker gerenciados (padrão)."
else
  case "$DATA_DIR" in "~"*) DATA_DIR="${HOME}${DATA_DIR#\~}" ;; esac
  mkdir -p "$DATA_DIR/qdrant" "$DATA_DIR/db" || die "Não foi possível criar $DATA_DIR."
  DATA_ABS="$(cd "$DATA_DIR" && pwd)"
  set_env "QDRANT_STORAGE" "$DATA_ABS/qdrant" "$COMPOSE_ENV"
  set_env "SQLITE_STORAGE" "$DATA_ABS/db" "$COMPOSE_ENV"
  set_env "DATABASE_URL" "sqlite:////data/openmemory.db" "$COMPOSE_ENV"
  ok "Armazenamento: $DATA_ABS (Qdrant em ./qdrant, SQLite em ./db)."
fi

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
