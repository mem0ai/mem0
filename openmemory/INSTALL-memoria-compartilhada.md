# Instalação — Memória Central Compartilhada (local-first)

Instalação única na rede local que sobe o servidor **MCP/API**, o **Qdrant**
(vector store, coleção única) e usa um **Ollama** local para LLM e embeddings.
Operação **100% local**: nenhuma dependência de serviços fora da rede (privacidade).

## Pré-requisitos

- Docker + Docker Compose.
- **Ollama** acessível na rede local (no host ou em outra máquina da LAN).

## Passos

1. **Configurar o ambiente**

   ```bash
   cd openmemory
   cp api/.env.example api/.env
   ```

2. **Detecção de modelos (task_09)** — descubra os modelos instalados no Ollama
   e preencha `LLM_MODEL` / `EMBEDDER_MODEL` no `api/.env`:

   ```bash
   curl http://<host-ollama>:11434/api/tags
   ```

   Ajuste também `OLLAMA_BASE_URL` em `api/.env` para o endereço do Ollama na
   rede (ex.: `http://192.168.0.10:11434`). Se o Ollama roda no mesmo host do
   Docker, o padrão `http://host.docker.internal:11434` já funciona.

3. **Subir o conjunto**

   ```bash
   docker compose up -d
   ```

   Sobem: `mem0_store` (Qdrant, porta 6333), `openmemory-mcp` (API/MCP, porta
   8765) e `openmemory-ui` (porta 3000).

4. **Validar a descoberta (task_08)** — os agentes se autoconfiguram via:

   ```bash
   curl http://<host>:8765/discovery
   ```

   O JSON traz `transport`, `base_url`, `route_template` e `fields`
   (`user_id` = hostname, `project` obrigatório).

## Variáveis de ambiente

| Variável | Função |
|----------|--------|
| `LLM_PROVIDER` / `LLM_MODEL` | Provedor/modelo do LLM (Ollama local). |
| `EMBEDDER_PROVIDER` / `EMBEDDER_MODEL` | Provedor/modelo de embeddings. |
| `OLLAMA_BASE_URL` | Endpoint do Ollama na rede local. |
| `QDRANT_HOST` / `QDRANT_PORT` | Qdrant (no compose, aponta para `mem0_store`). |
| `DATABASE_URL` | SQLite (catálogo + fila de escrita + histórico). |
| `OPENMEMORY_DISCOVERY_BASE_URL` | (Opcional) URL base anunciada em `/discovery`. |

## Persistência

- **Qdrant**: volume nomeado `mem0_storage` montado em `/qdrant/storage` — as
  memórias sobrevivem a reinícios do container.
- **SQLite**: persistido via bind mount `./api` (fila de escrita, catálogo de
  projetos e histórico).

## Fluxo ponta a ponta (smoke)

1. Um agente conecta na rota MCP `/mcp/{client_name}/sse/{hostname}`.
2. `add_memories(text, project)` **enfileira** e retorna ack imediato
   (`{status: queued, job_id}`) — sem bloquear (task_07).
3. O **worker** consome a fila, extrai via LLM e persiste no projeto (task_06).
4. `search_memory(query, project)` recupera a memória, **compartilhada** entre
   todas as máquinas (filtra por `project`, ignora hostname — task_03).
