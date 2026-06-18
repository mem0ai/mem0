# mem0-shared — Memória Central Compartilhada (local-first)

Fork do [mem0](https://github.com/mem0ai/mem0) adaptado para servir como **memória
central compartilhada de time**, rodando **100% na rede local**. Uma instalação
única sobe o servidor MCP/API, o vector store e usa um LLM local — nenhum
conteúdo de memória sai da rede.

> Este repositório **não** é o mem0 de origem com seus padrões de nuvem. As
> seções abaixo descrevem o que de fato existe e está ativo aqui. O SDK mem0
> original continua disponível como base (veja [Base: SDK mem0](#base-sdk-mem0)).

## Objetivo: por que este projeto existe

Times que trabalham com agentes de IA (Claude Code, Cursor, Codex) perdem
contexto o tempo todo: cada sessão começa do zero, cada máquina tem sua própria
"memória", e o conhecimento do time — decisões de arquitetura, convenções,
regras de negócio — não se acumula em lugar nenhum. As soluções de mercado
resolvem isso **na nuvem**, o que é inaceitável quando o conteúdo das memórias
inclui código proprietário, regras fiscais/financeiras e segredos do ERP.

Este projeto entrega uma **memória central, compartilhada e privada**: um único
acervo que todos os agentes do time leem e escrevem, rodando **100% na rede
local**, e que **escala de uma máquina a centenas de milhões de memórias** sem
nunca enviar conteúdo para fora. O alvo concreto é ~200 devs e dezenas de
agentes MCP sobre infraestrutura self-hosted.

## Como funciona: princípios de design (e o porquê de cada um)

Cada decisão da arquitetura existe para resolver um problema específico de
escala, privacidade ou qualidade — não por preferência técnica:

| Princípio | O que fazemos | Por que |
|-----------|---------------|---------|
| **Local-first, fail-closed** | O servidor **recusa subir** se o LLM/embedder apontar para um host não-local (`MEM0_LOCAL_ONLY=1`); telemetria desligada. | Privacidade é garantida em código, não em convenção: conteúdo sensível nunca sai da LAN, mesmo por engano de configuração. |
| **Escopo por `project`, não por máquina** | Memórias são chaveadas por `project`; o hostname serve só para atribuição/auditoria. | É o que torna a memória **compartilhada**: qualquer agente em qualquer host vê o mesmo acervo de um projeto. |
| **Escrita assíncrona com ack imediato** | `add_memories` enfileira e devolve `{queued, job_id}` na hora; um worker extrai via LLM depois. | O agente não pode travar esperando a extração LLM (lenta). A fila é durável e re-tenta em falha. |
| **Separar leitura de escrita** | Busca/embedding rodam no caminho da API; extração LLM roda em workers dedicados. | Embedding de busca (rápido, frequente) não compete por recursos com a extração LLM (pesada, em lote). |
| **Particionar por tenant** | Roteamento de coleção/shard por `project`; projetos gigantes promovidos a coleção dedicada. | Uma coleção única de centenas de milhões de vetores degrada a busca; particionar mantém cada índice pequeno e rápido. |
| **Governança de qualidade** | Quarentena reversível, TTL, dedup, consolidação semântica, teto por projeto e cold tier. | Em volume alto, a **qualidade** degrada junto com a performance: duplicatas e memórias velhas poluem a busca se não houver lifecycle. |
| **Operar com confiança** | CI que barra regressões, backup/restauração testáveis, tracing ponta a ponta, rate limit e auth por equipe. | "Funciona na demo" ≠ "pronto para produção": é preciso não regredir, não perder dados, diagnosticar e proteger o serviço. |

O resultado: latência sub-segundo na leitura, filas de escrita controladas e
privacidade self-hosted — mantendo o contrato MCP estável para os agentes.

## Estado atual do projeto

O fork evoluiu em **cinco fases** documentadas em `.docs/tasks/`. Todas as
tarefas planejadas estão **concluídas** no código e cobertas por testes
(suíte do `openmemory/api`: **375 passed, 2 skipped**).

| Fase | Escopo | Status | Referência |
|------|--------|--------|------------|
| **0** | Memória central local-first: escopo `project`, fila de escrita, worker embutido, discovery, provision, instaladores | Concluída | [`.docs/tasks/memoria-central-compartilhada/`](.docs/tasks/memoria-central-compartilhada/) |
| **1** | Escala self-hosted: PostgreSQL + PgBouncer, Redis (cache), write worker separado, Traefik, observabilidade | Concluída | [`.docs/tasks/self-hosted-scale-architecture/`](.docs/tasks/self-hosted-scale-architecture/) |
| **2** | Particionamento Qdrant por projeto: roteamento de coleção, migration worker (blue/green), promoção e admin | Concluída | [`.docs/tasks/particionamento-qdrant-fase2/`](.docs/tasks/particionamento-qdrant-fase2/) |
| **3** | Governança de qualidade: quarentena, TTL, dedup, consolidação, purge, políticas e governance-worker | Concluída | [`.docs/tasks/escala-governanca-fase3/`](.docs/tasks/escala-governanca-fase3/) |
| **Prontidão** | Production-readiness (LAN): gate de CI, backup/restauração, teto por projeto + cold tier, tracing OpenTelemetry, rate limit por projeto e auth por equipe | Concluída | [`.docs/tasks/prontidao-producao/`](.docs/tasks/prontidao-producao/) |

**Ainda fora de escopo** (decisão consciente para o alvo LAN — ver
[ADR-001](.docs/tasks/prontidao-producao/adrs/adr-001.md)): cluster Qdrant
multi-nó, autoscaling (HPA) e migração para Kubernetes; **uma coleção por
projeto** (hoje o isolamento é por tenant index/shard_key, que escala até
~100M vetores/coleção); embedding/LLM em GPU dedicada (TEI/vLLM); mTLS
service-to-service; e busca híbrida opcional. A resiliência sem cluster é
coberta por **backup/restauração** (single-node).

## O que isto entrega

### Memória compartilhada (Fase 0)

- **Memória compartilhada entre máquinas** — as memórias são escopadas por
  `project` (não por máquina). Qualquer agente em qualquer host lê e escreve no
  mesmo acervo; o hostname serve apenas para **atribuição/auditoria**.
- **Local-first e fail-closed** — o servidor **recusa inicializar** se o
  LLM/embedder configurado apontar para um host não-local (OpenAI, Anthropic
  etc.). A garantia é em código, não só em convenção (`MEM0_LOCAL_ONLY=1`).
- **Telemetria desligada** — `MEM0_TELEMETRY=false` e, com `MEM0_LOCAL_ONLY=1`,
  os eventos de uso (PostHog) do core são forçados a off antes do import do mem0.
- **Escrita assíncrona durável** — `add_memories` **enfileira** e devolve ack
  imediato (`{status: queued, job_id}`); um worker extrai via LLM e persiste.
  Falhas são re-enfileiradas até o teto de tentativas.
- **Auto-descoberta MCP** — agentes se autoconfiguram via `GET /discovery`
  (transporte, `base_url`, template de rota e campos esperados).
- **Detecção de modelos locais** — o instalador detecta **Ollama** (`/api/tags`)
  e **llama.cpp** (`/v1/models`) e deixa você escolher backend e modelos.

### Escala operacional (Fase 1)

- **PostgreSQL + PgBouncer** — catálogo, fila de escrita, auditoria e histórico
  migram do SQLite para PostgreSQL em modo escala.
- **Write worker separado** — a API/MCP não embute o consumidor da fila quando
  `RUN_EMBEDDED_WORKER=false`; workers dedicados processam a fila com
  `FOR UPDATE SKIP LOCKED`.
- **Cache Redis** — embeddings e resultados de busca com invalidação por escrita.
- **Traefik na borda** — rate limit, circuit breaker e sticky cookie para SSE/MCP.
- **Observabilidade** — `GET /health` e `GET /metrics` (Prometheus); stack
  opcional em `openmemory/compose/observability.yml`.

### Particionamento Qdrant (Fase 2)

- **Coleção por projeto** — projetos grandes podem migrar para coleções dedicadas
  via migration worker (perfil `migration`, execução sob demanda).
- **Admin de migração** — `POST /admin/migration/{start,validate,flip,rollback}`.
- **Promoção de projetos** — `POST /admin/projects/{name}/promote`.
- **Dual-write controlado** — cópia em background sem competir com o SLA da fila
  de escrita.

### Governança de qualidade (Fase 3)

- **Estados de memória** — `active`, `quarantined`, `purged` (metadados em
  PostgreSQL + payload `state` no Qdrant).
- **Busca filtrada** — `search`/`search_batch`/`keyword_search` no provider
  Qdrant aplicam `state=active` automaticamente; `list()` permanece sem filtro
  (jobs internos enxergam quarentenadas).
- **Quarentena reversível** — TTL por idade e inatividade; janela configurável
  antes do purge irreversível.
- **Jobs em background** — dedup, TTL prune, consolidação semântica (LLM),
  purge e avaliação de qualidade, agendados pelo governance-worker.
- **Políticas** — defaults globais em `Config(key="governance")` com overrides
  por projeto em `governance_policies`.

### Prontidão para produção (LAN)

Fechou os pontos que faltavam para operar com confiança em rede confiável:

- **Gate de CI** — os ~375 testes do `openmemory/api` rodam no `ci-gate.yml`
  (workflow `openmemory-api-ci.yml`) e **barram merges** com regressão.
- **Backup e restauração** — snapshot nativo do Qdrant + `pg_dump` para um
  object store **MinIO/S3** (sobrevive à falha do nó); endpoints
  `POST /admin/backup/{run,restore}` e `GET /admin/backup/status` (RPO), com
  [runbook de drill](openmemory/docs/runbooks/backup-restore.md) (RPO≤24h/RTO≤1h).
- **Teto por projeto (`max_memories`)** — job `enforce_quota`: em `alert` só
  reporta; em `enforce` quarentena os menos relevantes até o teto.
- **Cold tier** — job `cold_tier` arquiva projetos inativos (export para MinIO +
  remoção reversível) após `cold_tier_idle_days`.
- **Tracing distribuído** — OpenTelemetry instrumenta FastAPI/HTTPX/SQLAlchemy e
  exporta OTLP para Collector + Tempo; `trace_id` correlacionado nos logs.
- **Rate limit por `(project, hostname)`** — janela deslizante no Redis (busca
  30/min, escrita 60/min, burst 10/10s), substituindo o limite global do Traefik.
- **Autenticação por equipe** — `TeamAuthMiddleware` com modos `off`/`warn`/
  `enforce`; tokens vêm de secret (Docker secret), fora do `.env` versionado.

Verificação: a lógica (Python) é coberta por testes; a infraestrutura ao vivo
(MinIO, Collector/Tempo, PostgreSQL real) é validada por mocks nos testes e
pelos runbooks/drills em execução real. Runbooks em
[`openmemory/docs/runbooks/`](openmemory/docs/runbooks/).

## Perfis de deploy

| Perfil | Quando usar | Compose / script | Banco | Workers |
|--------|-------------|------------------|-------|---------|
| **Local-first** | Dev, time pequeno, uma máquina | `install.py` → `openmemory/docker-compose.yml` | SQLite | Worker embutido na API |
| **Escala (Compose)** | LAN com dezenas de agentes, PostgreSQL | `openmemory/scripts/bootstrap-scale.sh` → `docker-compose.scale.yml` | PostgreSQL + PgBouncer | API (réplicas via uvicorn), write-worker; migration-worker sob demanda (`--profile migration`) |
| **Escala (Swarm)** | Produção com réplicas explícitas | `docker stack deploy -c docker-stack.yml mem0` | PostgreSQL + PgBouncer | API ×4, write-worker ×8, **governance-worker ×1** |

> O **governance-worker** está no `docker-stack.yml` (Swarm). No
> `docker-compose.scale.yml` ele ainda não entra — rode manualmente:
> `python -m app.workers.governance_worker` com as mesmas variáveis da API.

## Arquitetura

### Modo local-first (Fase 0)

```
Agentes (Claude Code, Cursor, …)
        │  MCP  /mcp/{client_name}/sse/{hostname}
        ▼
┌─────────────────────────────┐
│ openmemory-mcp  (API/MCP)   │  :8765   FastAPI + MCP + worker de escrita
│  ├─ fila de escrita (SQLite)│          catálogo de projetos + auditoria
│  └─ guard fail-closed       │          (MEM0_LOCAL_ONLY)
└──────────┬──────────────────┘
           │
   ┌───────┴────────┐
   ▼                ▼
Qdrant          LLM local
(:6333)         Ollama (:11434) ou llama.cpp (OpenAI-compat)
coleção única   extração + embeddings
```

### Modo escala (Fases 1–3)

```
Agentes ──► Traefik (:8765) ──► openmemory-mcp (N réplicas, stateless)
                    │                    │
                    │                    ├── Redis (cache embed/search)
                    │                    └── Qdrant (coleção base ou por project)
                    │
        openmemory-write-worker (N) ──► fila PostgreSQL ──► LLM local
        openmemory-governance-worker (1) ──► jobs dedup/TTL/consolidate/purge
        openmemory-migration-worker (on-demand) ──► blue/green por project
                    │
              PostgreSQL + PgBouncer (catálogo, fila, governança, audit)
```

Fluxo ponta a ponta (comum aos dois perfis):

1. Um agente conecta na rota MCP `/mcp/{client_name}/sse/{hostname}`.
2. `add_memories(text, project)` **enfileira** e retorna ack imediato.
3. O **write worker** consome a fila, extrai via LLM e persiste no projeto.
4. `search_memory(query, project)` recupera memórias **ativas** do projeto
   compartilhado (quarentenadas ficam fora da busca semântica).
5. O **governance-worker** aplica políticas (TTL, dedup, consolidação) em
   background conforme agendamento e enfileiramento via `/admin/governance/*`.

## Instalação

### Local-first (1 comando)

Pré-requisitos: **Docker + Docker Compose v2** e um backend de LLM local
acessível na rede (**Ollama** e/ou **llama.cpp**).

Multiplataforma (Linux/macOS/Windows), na raiz do projeto — só precisa de
Python 3.8+ e Docker:

```bash
python install.py
```

Linux (bash), a partir de `openmemory/`:

```bash
cd openmemory
./install-local-first.sh
```

O instalador confere pré-requisitos, prepara os `.env`, detecta os modelos
locais, deixa você escolher backend/modelos, sobe o conjunto e valida a
auto-descoberta. Variações úteis:

```bash
# Ollama em outra máquina da LAN:
python install.py --ollama-url http://192.168.0.10:11434

# Forçar llama.cpp (servidor OpenAI-compatível):
python install.py --backend llamacpp --llamacpp-url http://192.168.0.10:8080

# Token/API key do backend local (opcional — Ollama dispensa):
python install.py --api-key SEU_TOKEN

# Escolher onde as memórias ficam no host (Qdrant + SQLite):
python install.py --data-dir /srv/mem0-data

# Não-interativo (CI / provisionamento):
python install.py --llm llama3.1:latest --embedder nomic-embed-text --yes

# Manter modelos do .env / também subir a UI:
python install.py --skip-models --with-ui
```

Sobem três serviços: `mem0_store` (Qdrant, `:6333`), `openmemory-mcp`
(API/MCP, `:8765`) e `openmemory-ui` (`:3000`, opcional).

> ⚠️ O `openmemory/run.sh` é o instalador **do upstream mem0** e **não é
> local-first** (exige `OPENAI_API_KEY`). Para o fluxo deste projeto use
> **`install.py`** / **`install-local-first.sh`**.

Guia completo:
[`openmemory/INSTALL-memoria-compartilhada.md`](openmemory/INSTALL-memoria-compartilhada.md).

### Escala (PostgreSQL + workers)

A partir de `openmemory/`:

```bash
cd openmemory
./scripts/bootstrap-scale.sh
# opcional: migrar SQLite existente
./scripts/bootstrap-scale.sh --migrate-sqlite /caminho/openmemory.db
docker compose -f docker-compose.scale.yml up -d
```

Para migração de particionamento (Fase 2):

```bash
docker compose -f docker-compose.scale.yml --profile migration run --rm openmemory-migration-worker
```

Arquitetura alvo e decisões:
[`openmemory/docs/self-hosted-scale-architecture.md`](openmemory/docs/self-hosted-scale-architecture.md).

## Validação (smoke test)

```bash
cd openmemory
./scripts/smoke-memoria-compartilhada.sh            # sobe, valida e derruba
KEEP_UP=1 ./scripts/smoke-memoria-compartilhada.sh  # mantém no ar após validar
```

## Conectar um agente ao servidor de memória

Com o servidor no ar (`:8765`), um agente consegue instalar o MCP e os hooks
sozinho a partir de um único prompt. O endpoint `/provision` devolve um manifesto
com tudo que precisa ser feito: bloco de config MCP, variáveis de ambiente, modos
de memória para o usuário escolher — e uma receita de passos ordenados.

### Prompt para o agente (Claude Code, Cursor ou Codex)

Substitua `SERVIDOR` pelo endereço real e envie para o agente:

**Claude Code:**
```
Leia http://SERVIDOR:8765/provision?host=claude-code e execute a receita
retornada: escreva o bloco MCP no arquivo indicado (substituindo {hostname}
pelo hostname desta máquina), defina as variáveis de ambiente do campo "env",
apresente ao usuário as 3 opções de modo de memória e grave a escolha em
~/.mem0/settings.json. Confirme cada ação mutante com o usuário antes de executar.
```

**Cursor:**
```
Leia http://SERVIDOR:8765/provision?host=cursor e execute a receita retornada:
escreva o bloco MCP no arquivo indicado, defina as variáveis de ambiente do
campo "env", apresente as 3 opções de modo de memória e grave a escolha em
~/.mem0/settings.json. Confirme cada ação com o usuário antes de executar.
```

**Codex:**
```
Leia http://SERVIDOR:8765/provision?host=codex e execute a receita retornada:
escreva o bloco MCP no arquivo indicado, defina as variáveis de ambiente do
campo "env", apresente as 3 opções de modo de memória e grave a escolha em
~/.mem0/settings.json. Confirme cada ação com o usuário antes de executar.
```

O agente vai:
1. Escrever/mesclar o bloco MCP no arquivo do host (`.mcp.json`, `.cursor/mcp.json`
   ou `~/.codex/config.toml`), substituindo `{hostname}` pelo hostname da máquina.
2. Definir `OPENMEMORY_API_BASE`, `MEM0_LOCAL_ONLY=1`, `MEM0_API_KEY=local` e
   `MEM0_TELEMETRY=false` no local correto para o host.
3. Apresentar os 3 modos de memória e gravar a escolha em `~/.mem0/settings.json`.
4. Verificar com `GET /discovery` e um `POST /v3/memories/search/` de teste.

> **Claude Code com o plugin instalado** (`integrations/mem0-plugin`) não precisa
> deste passo — os hooks de sessão conectam automaticamente via `OPENMEMORY_API_BASE`.

### Ferramentas MCP disponíveis após a conexão

| Ferramenta | Descrição |
|------------|-----------|
| `add_memories(text, project)` | Enfileira escrita assíncrona. Retorna `{"status":"queued","job_id":"..."}` imediatamente — não bloqueia. |
| `get_job_status(job_id)` | Consulta status de um job (`queued / processing / done / failed`) e o erro, se houver. |
| `search_memory(query, project)` | Busca semântica por similaridade. Retorna memórias **ativas** do projeto compartilhado. |
| `list_memories(project)` | Lista memórias do projeto (inclui quarentenadas — uso operacional/admin). |
| `delete_memories(memory_ids)` | Remove memórias específicas por ID. |
| `delete_all_memories()` | Remove todas as memórias acessíveis ao agente atual. |

> `project` é **obrigatório** em todas as ferramentas de leitura e escrita. Define
> o espaço compartilhado: memórias gravadas por qualquer agente em `project="X"` são
> visíveis a todos que buscam em `project="X"`, independente de hostname.

---

## Governança de memória

Política efetiva = defaults globais + override por projeto. Valores padrão
(ajustáveis via API):

| Parâmetro | Default | Efeito |
|-----------|---------|--------|
| `ttl_max_age_days` | 365 | Quarentena por idade máxima |
| `ttl_idle_days` | 90 | Quarentena por inatividade |
| `quarantine_window_days` | 30 | Janela antes do purge |
| `consolidation_enabled` | `false` | Consolidação semântica via LLM |
| `similarity_threshold` | 0.92 | Limiar para dedup/consolidação |
| `protected_categories` | `decision`, `security` | Categorias imunes a TTL/purge automático |
| `max_memories` | `null` | Teto de memórias ativas por projeto (`null` = sem teto) |
| `max_memories_action` | `alert` | `alert` (só métrica) ou `enforce` (quarentena até o teto) |
| `cold_tier_idle_days` | 180 | Inatividade que qualifica um projeto para cold tier |

Jobs disponíveis: `dedup`, `ttl_prune`, `consolidate`, `purge`, `quality_eval`,
`enforce_quota`, `cold_tier`.

## Endpoints operacionais

| Prefixo | Uso |
|---------|-----|
| `GET /discovery` | Auto-config MCP |
| `GET /provision` | Receita de instalação para agentes |
| `GET /health` | Health check (modo escala) |
| `GET /metrics` | Métricas Prometheus |
| `POST /admin/backup/run` | Dispara backup (Qdrant + PostgreSQL → MinIO/S3) |
| `POST /admin/backup/restore` | Restaura a partir de um prefixo de backup |
| `GET /admin/backup/status` | Último backup, total de objetos e RPO corrente |
| `GET/PUT /admin/governance/policies` | Política global |
| `PUT /admin/governance/policies/{project}` | Override por projeto |
| `POST /admin/governance/jobs/{job_type}` | Enfileirar job (`dedup`, `ttl_prune`, …) |
| `GET /admin/governance/audit` | Histórico de transições de estado |
| `POST /admin/governance/revert/{memory_id}` | Reverter quarentena |
| `GET /admin/governance/quality` | Última avaliação de qualidade |
| `GET /admin/projects/sizes` | Tamanho por projeto/coleção |
| `POST /admin/migration/*` | Controle blue/green de particionamento |
| `POST /admin/projects/{name}/promote` | Promover projeto para coleção dedicada |

## Configuração essencial (`openmemory/api/.env`)

| Variável | Função |
|----------|--------|
| `MEM0_LOCAL_ONLY=1` | Guard fail-closed: recusa subir se LLM/embedder não for local. |
| `MEM0_TELEMETRY=false` | Desliga telemetria do core (forçado quando local-only). |
| `LLM_PROVIDER` / `LLM_MODEL` | Provedor/modelo do LLM (Ollama por padrão). |
| `EMBEDDER_PROVIDER` / `EMBEDDER_MODEL` | Provedor/modelo de embeddings. |
| `OLLAMA_BASE_URL` / `OLLAMA_LLM_URL` / `OLLAMA_EMBED_URL` | Endpoints Ollama (modo escala separa LLM e embed). |
| `QDRANT_HOST` / `QDRANT_PORT` | Qdrant (no compose, aponta para `mem0_store`). |
| `DATABASE_URL` | SQLite (local) ou `postgresql://…@pgbouncer:5432/openmemory` (escala). |
| `REDIS_URL` | Cache de leitura (modo escala). |
| `RUN_EMBEDDED_WORKER` | `true` (default local) ou `false` quando write worker é externo. |
| `GOVERNANCE_ENABLE_SCHEDULER` | `true` no governance-worker para agendamento interno. |
| `QDRANT_STORAGE` / `SQLITE_STORAGE` | Volumes de dados no host (instalador `--data-dir`). |
| `OPENMEMORY_DISCOVERY_BASE_URL` | (Opcional) URL base anunciada em `/discovery`. |
| `AUTH_MODE` | Auth por equipe: `off` / `warn` (default) / `enforce`. |
| `AUTH_TOKENS_FILE` / `AUTH_TOKENS` | Origem dos tokens por equipe (secret montado ou inline). |
| `RL_SEARCH_PER_MIN` / `RL_WRITE_PER_MIN` / `RL_BURST` | Limites de rate limit por `(project, hostname)`. |
| `S3_ENDPOINT` / `S3_BUCKET` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Object store de backup/cold tier (MinIO/S3). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_SDK_DISABLED` | Tracing OpenTelemetry (endpoint do Collector; desativar). |

Backends locais suportados: **Ollama** (provider `ollama`) e **llama.cpp** (via
provider `openai` apontando para o servidor OpenAI-compatível). Veja
`openmemory/api/.env.example` para exemplos.

## Modo de memória dos agentes

A automação dos hooks de memória do plugin tem 3 modos, gravados em
`~/.mem0/settings.json` (o MCP e os comandos manuais funcionam nos três):

| Modo | Efeito |
|------|--------|
| **1. Ler + gravar** | Busca memórias e captura aprendizados automaticamente. |
| **2. Ler; gravar manual** | Injeta contexto automático; só grava quando solicitado (default recomendado). |
| **3. Manual** | Nada automático; tudo via comandos `/mem0:*` e MCP. |

Detalhes em [`integrations/mem0-plugin/skills/mode/SKILL.md`](integrations/mem0-plugin/skills/mode/SKILL.md).

## Testes

```bash
# OpenMemory API (375 passed, 2 skipped — governança, particionamento, escala,
# backup, tracing, rate limit, auth). Os 2 skips exigem POSTGRES_TEST_URL.
cd openmemory/api && pytest tests/

# SDK Python — escopo project + Qdrant governance filter
pytest tests/memory/test_project_scope.py tests/vector_stores/test_qdrant.py
```

Suítes relevantes: `test_governance_*`, `test_quarantine`, `test_partition_*`,
`test_migration_*`, `test_write_queue*`, `test_local_only_guard`, `test_discovery`,
`test_backup*`, `test_quota`, `test_cold_tier`, `test_tracing`, `test_rate_limit`,
`test_team_auth`, `test_alerts`. Os mesmos testes rodam no CI (`ci-gate.yml`).

## Documentação interna

| Caminho | Conteúdo |
|---------|----------|
| [`.docs/tasks/memoria-central-compartilhada/`](.docs/tasks/memoria-central-compartilhada/) | PRD, TechSpec, ADRs — Fase 0 |
| [`.docs/tasks/self-hosted-scale-architecture/`](.docs/tasks/self-hosted-scale-architecture/) | PRD, TechSpec, ADRs — Fase 1 |
| [`.docs/tasks/particionamento-qdrant-fase2/`](.docs/tasks/particionamento-qdrant-fase2/) | PRD, TechSpec, ADRs — Fase 2 |
| [`.docs/tasks/escala-governanca-fase3/`](.docs/tasks/escala-governanca-fase3/) | PRD, TechSpec, ADRs — Fase 3 |
| [`.docs/tasks/prontidao-producao/`](.docs/tasks/prontidao-producao/) | PRD, TechSpec, ADRs — Prontidão para produção |
| [`openmemory/docs/runbooks/`](openmemory/docs/runbooks/) | Runbooks: backup/restore, auth/secrets, governança, incidente |
| [`openmemory/INSTALL-memoria-compartilhada.md`](openmemory/INSTALL-memoria-compartilhada.md) | Instalação local-first detalhada |
| [`openmemory/docs/self-hosted-scale-architecture.md`](openmemory/docs/self-hosted-scale-architecture.md) | Arquitetura alvo, roadmap e estado de implementação (§15) |
| [`AGENTS.md`](AGENTS.md) | Monorepo mem0 upstream (build, lint, CI) |

## Principais mudanças em relação ao upstream

| Área | Mudança |
|------|---------|
| `mem0/memory/main.py` | Campo `project` em `add`/`search` (escopo compartilhado). |
| `mem0/vector_stores/qdrant.py` | Filtro `state=active` em buscas; roteamento por coleção/partição. |
| `openmemory/api/app/workers/` | Write worker, migration worker, governance worker. |
| `openmemory/api/app/utils/write_queue.py` | Fila durável (SQLite ou PostgreSQL) com retentativas. |
| `openmemory/api/app/utils/governance_*.py` | Política, fila e quarentena (Fase 3). |
| `openmemory/api/app/governance/` | Jobs dedup, TTL, purge, consolidação, quality eval. |
| `openmemory/api/app/routers/admin.py` | Migração e promoção de projetos (Fase 2). |
| `openmemory/api/app/routers/governance.py` | Admin de governança (Fase 3). |
| `openmemory/api/app/routers/discovery.py` | `GET /discovery` para auto-config MCP. |
| `openmemory/api/app/routers/provision.py` | Provisionamento local-first. |
| `openmemory/api/app/governance/{quota,cold_tier}.py` | Teto por projeto e cold tier (Prontidão). |
| `openmemory/api/app/utils/backup.py` + `routers/admin.py` | Backup/restauração para MinIO/S3. |
| `openmemory/api/app/utils/tracing.py` | Tracing OpenTelemetry (Prontidão). |
| `openmemory/api/app/middleware/{rate_limit,team_auth}.py` | Rate limit por projeto e auth por equipe. |
| `.github/workflows/openmemory-api-ci.yml` | Gate de CI dos testes do `openmemory/api`. |
| `openmemory/docker-compose.scale.yml` | Stack de escala (Compose). |
| `openmemory/docker-stack.yml` | Stack de escala (Swarm, inclui governance-worker). |
| `install.py` / `openmemory/install-local-first.sh` | Instaladores local-first. |
| `openmemory/scripts/bootstrap-scale.sh` | Bootstrap idempotente do modo escala. |

## Base: SDK mem0

Por baixo, este projeto continua sendo o monorepo mem0 (SDK Python `mem0`, SDK
TypeScript `mem0-ts`, CLIs, servidor e integrações). Para detalhes de
desenvolvimento do SDK, estrutura do monorepo, comandos de build/lint/test e
padrões de código, veja [`AGENTS.md`](AGENTS.md).

- Documentação do mem0 de origem: https://docs.mem0.ai
- Repositório de origem: https://github.com/mem0ai/mem0

## Licença

Apache 2.0 — veja [LICENSE](LICENSE).
