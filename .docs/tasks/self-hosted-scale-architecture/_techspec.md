# TechSpec — Arquitetura self-hosted em escala para Mem0/OpenMemory

> **Idioma:** PT-BR. **Status:** rascunho para revisão. **Data:** 2026-06-16. **Entrada:** [_prd.md](_prd.md).

## Resumo Executivo

Esta TechSpec detalha o MVP (Fases 0+1 do PRD): remover os dois maiores gargalos — embedding inline e escrita acoplada — entregando latência de leitura sub-segundo e estabilidade sob a carga de 200 devs, no ambiente Docker Swarm / VMs. A estratégia reusa ao máximo o código existente: o embedding e o LLM passam a **serviços Ollama dedicados e replicados** acessados por `base_url` (sem novo código de provider, [ADR-002](adrs/adr-002.md)); a fila de escrita migra de SQLite para **PostgreSQL com `FOR UPDATE SKIP LOCKED`** e os workers saem do processo da API para um **serviço separado** ([ADR-003](adrs/adr-003.md)); um **reverse proxy (Traefik/Nginx)** assume rate limit, circuit breaker e sticky sessions para o MCP SSE ([ADR-004](adrs/adr-004.md)); e um **cache Redis de embedding + resultado de busca** com invalidação por escrita torna-se a principal alavanca de latência ([ADR-005](adrs/adr-005.md)). Observabilidade via Prometheus/Grafana + `/health`. Para preservar o requisito de instalação simplificada apesar do número de componentes, o stack sobe com **um comando + bootstrap script** idempotente que provisiona banco, migrations, índices e configuração ([ADR-006](adrs/adr-006.md)).

**Trade-off técnico principal**: ao manter Ollama (em vez de TEI/vLLM) priorizamos menor mudança de stack e a continuidade do self-hosted local-only, ao custo de throughput de embedding inferior — compensado por cache agressivo e réplicas, não por batching contínuo. A consequência é uma dependência forte do cache para atingir a meta de p99; com cache frio sob pico, a latência depende do dimensionamento das réplicas de Ollama.

## Arquitetura do Sistema

### Visão dos Componentes

| Componente | Tipo | Responsabilidade |
|------------|------|------------------|
| **Reverse proxy** (Traefik/Nginx) | Novo | Borda: LB das réplicas, rate limit, circuit breaker, sticky sessions SSE |
| **mem0-mcp-api** | Modificado | API stateless (MCP SSE/HTTP + compat_v3); leitura com cache; enfileira escrita. Sem worker embutido |
| **mem0-write-worker** | Novo (extraído) | Processo separado; consome fila PostgreSQL; extração LLM + upsert Qdrant; invalida cache |
| **embed-service** | Novo (dedicado) | Serviço de embedding local replicado — Ollama ou llama.cpp (OpenAI-compatible) |
| **llm-service** | Novo (dedicado) | Serviço de extração local replicado — Ollama ou llama.cpp; recurso separado do embedding |
| **Redis** | Novo | Cache de embedding (TTL 1–24h) + cache de resultado de busca (TTL ~5min) |
| **PostgreSQL + PgBouncer** | Novo (migra SQLite) | Fila durável, catálogo, auditoria, histórico; pooling de conexões |
| **Qdrant** | Mantido | Vector store (coleção única, conforme ADR-003 da task de memória) |
| **Prometheus + Grafana** | Novo | Métricas, painéis, alertas |
| **Stack Swarm + bootstrap script** | Novo | Instalação automatizada: 1 comando sobe tudo; provisiona DB, roda migrations, cria índices Qdrant, aplica config por template, valida `/health` ([ADR-006](adrs/adr-006.md)) |

### Fluxo de dados

**Leitura (`search_memory`)**: Cliente MCP → reverse proxy (rate limit, sticky) → API → cache de resultado (hit → retorna) → cache de embedding (hit → pula inferência) → `embed-service` (miss) → Qdrant `query_points` → grava caches → resposta.

**Escrita (`add_memories`)**: Cliente MCP → reverse proxy → API valida → enfileira no PostgreSQL (`job_id`) → ack imediato. `mem0-write-worker` faz dequeue (`SKIP LOCKED`) → `llm-service` (extração) → `embed-service` (batch) → Qdrant upsert → invalida cache de busca do `project` → marca `done`/retry.

### Interações externas

Nenhuma fora do perímetro self-hosted. Todos os serviços rodam na VPC/rede interna; nenhum dado sai para serviços de terceiros (mantém o requisito de privacidade do PRD).

## Design de Implementação

### Interfaces Principais

**1. Configuração do cliente mem0 apontando para serviços dedicados** — reuso de [memory.py](openmemory/api/app/utils/memory.py), apenas via env/config:

```python
# Embedding e LLM como serviços Ollama dedicados (ADR-002) — sem código novo
config = {
    "embedder": {
        "provider": "ollama",
        "config": {"model": "nomic-embed-text", "ollama_base_url": OLLAMA_EMBED_URL},
    },
    "llm": {
        "provider": "ollama",
        "config": {"model": "llama3.1:8b", "ollama_base_url": OLLAMA_LLM_URL},
    },
    "vector_store": {"provider": "qdrant", "config": {"host": QDRANT_HOST, "port": 6333}},
}
# Modo duplo decidido na INSTALAÇÃO, multi-backend (Ollama OU llama.cpp):
#  - produção: provisionamento grava endpoints explícitos dos serviços dedicados (precedência).
#  - dev/single-host: install sonda Ollama (/api/tags) e llama.cpp (llama-server /v1/models) e grava o detectado.
# llama.cpp pluga via provider "openai" + openai_base_url (sem novo provider); Ollama via provider "ollama".
```

**2. Camada de cache de leitura** — novo módulo `app/utils/read_cache.py`:

```python
class ReadCache:
    """Cache Redis de embedding e de resultado de busca (ADR-005)."""

    def get_embedding(self, model: str, query: str) -> list[float] | None: ...
    def set_embedding(self, model: str, query: str, vector: list[float]) -> None: ...  # TTL 1-24h

    def get_search(self, project: str, query: str, top_k: int, filter_hash: str) -> list[dict] | None: ...
    def set_search(self, project: str, query: str, top_k: int, filter_hash: str, hits: list[dict]) -> None: ...  # TTL ~5min

    def invalidate_search(self, project: str) -> None: ...  # chamado pelo worker após upsert
```

**3. Dequeue seguro para concorrência** — evolução de [write_queue.py](openmemory/api/app/utils/write_queue.py):

```python
def dequeue(self, limit: int = 1) -> list[WriteJob]:
    """Retorna até `limit` jobs 'queued', marcando-os 'processing'.
    PostgreSQL: SELECT ... FOR UPDATE SKIP LOCKED garante entrega única entre workers (ADR-003)."""
    rows = (
        db.query(WriteQueueModel)
        .filter(WriteQueueModel.status == WriteQueueStatus.queued)
        .order_by(WriteQueueModel.created_at.asc())
        .with_for_update(skip_locked=True)   # no-op em SQLite; ativo em PostgreSQL
        .limit(limit)
        .all()
    )
    for row in rows:
        row.status = WriteQueueStatus.processing
    db.commit()
    return [_to_job(row) for row in rows]
```

### Modelos de Dados

Sem novas entidades de domínio no MVP. Mudanças:

- **`WriteQueueJob`** ([models.py](openmemory/api/app/models.py)): inalterado em schema; passa a residir no PostgreSQL. Índice `idx_write_queue_status_created` mantido (crítico para o dequeue ordenado).
- **`Project`**, **`WriteAuditLog`**: migram para PostgreSQL sem mudança de schema.
- **Chaves de cache (Redis)**:
  - Embedding: `embed:v1:{model}:{sha256(query_normalizada)}` → vetor; TTL 1–24h.
  - Resultado: `search:v1:{project}:{sha256(query)}:{top_k}:{filter_hash}` → lista de hits; TTL ~5min.
- **`database.py`**: `check_same_thread` condicionado ao dialeto SQLite; para PostgreSQL, configurar engine sem esse `connect_arg`.

### Endpoints de API

Contrato MCP e compat_v3 **inalterados** (sem mudança para os agentes). A **instalação fácil do cliente é preservada**: os endpoints de auto-descoberta/provisionamento (`/discovery`, `/.well-known/mcp`) e os hooks do plugin (compat_v3, caminho síncrono que mantém `type`/`file`) continuam funcionando exatamente como hoje. A única diferença, transparente para o cliente, é que a descoberta passa a **anunciar a URL do reverse proxy** (ponto de entrada único, com sticky sessions para o SSE) em vez de um host direto; por trás do endpoint há N réplicas.

Novos endpoints operacionais:

| Método | Caminho | Descrição | Response |
|--------|---------|-----------|----------|
| GET | `/health` | Liveness/readiness: DB, Qdrant, cliente mem0, profundidade de fila | `200` `{status, checks}` / `503` se degradado |
| GET | `/metrics` | Métricas Prometheus (latência, fila, cache, erros) | `200` formato Prometheus |

## Pontos de Integração

| Serviço | Propósito | Auth | Erros / Retry |
|---------|-----------|------|---------------|
| `embed-service` (Ollama/llama.cpp) | Embedding de queries e fatos | Rede interna | Timeout + circuit breaker na borda; fallback: cache |
| `llm-service` (Ollama/llama.cpp) | Extração de fatos na escrita | Rede interna | Retry/backoff do worker (`max_attempts`) |
| Qdrant | Busca e upsert de vetores | Rede interna | Circuit breaker; erro propagado ao job (retry) |
| Redis | Cache de leitura | Rede interna | Degradação graciosa: miss = caminho normal (cache nunca bloqueia leitura) |
| PostgreSQL via PgBouncer | Fila, catálogo, auditoria | Credenciais/Secret | Pool transaction-mode; falha = erro 503 na escrita |

## Análise de Impacto

| Componente | Tipo de Impacto | Descrição e Risco | Ação Necessária |
|------------|-----------------|-------------------|-----------------|
| [memory.py](openmemory/api/app/utils/memory.py) | modificado | Apontar embedder/LLM para serviços dedicados via env (modo produção); preservar auto-detecção no host como fallback dev/single-host. Risco baixo | Configurar env com precedência; manter `_fix_ollama_urls`/detecção `/api/tags` quando base_url não for explícito; validar local-only guard com base_url privada |
| [write_queue.py](openmemory/api/app/utils/write_queue.py) | modificado | `dequeue` com `SKIP LOCKED`. Risco médio (corrida entre workers) | Implementar + teste de concorrência |
| [write_worker.py](openmemory/api/app/workers/write_worker.py) | modificado | `max_concurrency` via env; invalidação de cache pós-upsert. Risco baixo | Parametrizar; chamar `invalidate_search` |
| [main.py](openmemory/api/main.py) | modificado | Remover/gate startup hook do worker; registrar `/health`, `/metrics`. Risco médio | Gate por env `RUN_EMBEDDED_WORKER` |
| Novo entrypoint worker | novo | `python -m app.workers.write_worker`. Risco baixo | Criar script + serviço Swarm |
| `app/utils/read_cache.py` | novo | Cache Redis de leitura. Risco médio (invalidação/stale) | Implementar + testes |
| [mcp_server.py](openmemory/api/app/mcp_server.py) | modificado | Integrar cache no `search_memory`. Risco médio (latência/correção) | Wrappar embedding+busca no cache |
| [discovery.py](openmemory/api/app/routers/discovery.py) | modificado | Anunciar a URL do reverse proxy (entrypoint único) na descoberta; install do cliente e hooks inalterados. Risco baixo | Configurar URL pública anunciada via env |
| [compat_v3.py](openmemory/api/app/routers/compat_v3.py) | mantido | Hooks do plugin preservados (caminho síncrono, metadados `type`/`file`). Risco baixo | Nenhuma mudança de contrato |
| [database.py](openmemory/api/app/database.py) | modificado | `check_same_thread` condicional ao dialeto. Risco baixo | Ajustar engine |
| Alembic | modificado | Validar migrations em PostgreSQL. Risco médio | Rodar/migrar dados existentes |
| docker-compose / Swarm stack | novo | Reverse proxy, Redis, PostgreSQL+PgBouncer, 2× Ollama, Prometheus/Grafana. Risco alto (orquestração) | Escrever stack Swarm + docs VMs |
| Bootstrap script + config templating | novo | Instalação automatizada: provisiona DB, migrations, índices Qdrant, env por template, gate `/health`. Risco médio (idempotência, ordem) | Implementar script idempotente + healthchecks |

## Abordagem de Testes

### Testes Unitários

- **`dequeue` com `SKIP LOCKED`**: simular múltiplos workers concorrentes; garantir que nenhum job é entregue duas vezes nem perdido.
- **`ReadCache`**: hit/miss de embedding e de busca; invalidação por `project`; degradação graciosa quando Redis indisponível (miss, nunca exceção).
- **`WriteWorker`**: `max_concurrency` configurável; retry/backoff até `max_attempts`; invalidação de cache chamada após upsert.
- **Normalização de query**: trim/lowercase/whitespace consistente entre cache de embedding e de busca.
- Mocks: cliente Ollama, Qdrant e Redis isolados; PostgreSQL com banco de teste.

### Testes de Integração

- **Fila ponta a ponta em PostgreSQL**: enqueue (API) → dequeue concorrente por N workers → upsert Qdrant → invalidação de cache → `done`.
- **Caminho de leitura com cache**: cache frio (miss → Ollama → Qdrant) vs quente (hit) medindo latência.
- **Migração SQLite → PostgreSQL**: validar dados de `write_queue`, `projects`, `write_audit_logs`.
- **Borda**: rate limit dispara sob rajada; sticky session mantém sessão SSE na mesma réplica.
- **Teste de carga**: simular ~200 clientes (QPS de busca e taxa de escrita a definir — pergunta em aberto do PRD) e validar metas de p99 e lag de fila.

## Sequenciamento de Desenvolvimento

### Ordem de Construção

1. **Fundação PostgreSQL** — `database.py` (dialeto condicional) + validar Alembic em PostgreSQL + PgBouncer. Sem dependências.
2. **`dequeue` com `SKIP LOCKED`** — evoluir `write_queue.py`. Depende do passo 1.
3. **Worker como processo separado** — entrypoint + gate do startup hook + `max_concurrency` via env. Depende do passo 2.
4. **Serviços de inferência dedicados** — configurar `embed-service` e `llm-service` (Ollama ou llama.cpp); apontar `memory.py` via env/provider (`ollama` ou `openai`+`base_url`). Independente dos passos 1–3 (pode correr em paralelo), mas integra no passo 6.
5. **Cache Redis (`ReadCache`)** — módulo + integração no `search_memory` e invalidação no worker. Depende dos passos 3 e 4.
6. **Reverse proxy + réplicas** — Traefik/Nginx com rate limit, circuit breaker, sticky SSE; API em N réplicas. Depende dos passos 4 e 5.
7. **Observabilidade** — `/health`, `/metrics`, Prometheus/Grafana, alertas. Depende dos passos 3, 5 e 6 (instrumenta os caminhos prontos).
8. **Stack único + bootstrap automatizado** — arquivo de stack Swarm (e instruções VMs) que sobe tudo com um comando; bootstrap script idempotente provisiona o PostgreSQL, roda `alembic upgrade head`, cria índices Qdrant, aplica config por template de env (decidindo modo escala vs dev/single-host) e valida `/health` antes de liberar a borda; janela de migração de dados SQLite→PostgreSQL como passo guiado ([ADR-006](adrs/adr-006.md)). Depende de todos os anteriores.

### Dependências Técnicas

- **Hardware/GPU** para os dois serviços Ollama (pergunta em aberto do PRD) — bloqueante para os passos 4 e 6.
- **PostgreSQL + PgBouncer** provisionados — bloqueante para o passo 1.
- **Cluster Redis** provisionado — bloqueante para o passo 5.
- **Definição dos alvos de carga** (QPS busca / taxa escrita) — bloqueante para o teste de carga (passo 8).

## Monitoramento e Observabilidade

Métricas-chave (Prometheus) e alertas:

| Métrica | Alerta |
|---------|--------|
| `mcp_search_latency_p99` | > 100 ms (quente) / > 300 ms (frio) |
| `embed_cache_hit_rate` | < 30% |
| `search_cache_hit_rate` | (acompanhar) |
| `write_queue_depth` / `write_queue_lag_seconds` | lag p95 > 60 s |
| `write_worker_error_rate` | > 5% |
| `qdrant_search_latency_p99` | > 200 ms |
| `ollama_embed_latency` | (acompanhar saturação) |

- **`/health`**: checagens de DB, Qdrant, cliente mem0 e profundidade de fila; consumido pelo reverse proxy/Swarm.
- **Logs estruturados** com `request_id`/`job_id` para correlação entre leitura e escrita.
- Painel Grafana com as metas do PRD (p99, lag, hit rate) como linha de base de sucesso.

## Considerações Técnicas

### Decisões-Chave

- **Decisão**: inferência local dedicada/replicada (Ollama **ou llama.cpp**) em vez de TEI/vLLM, com **modo duplo decidido no provisionamento** e **auto-detecção multi-backend** no install (Ollama via `/api/tags`; llama.cpp via `llama-server` OpenAI-compatible). Em escala, grava endpoints explícitos; em dev/single-host, detecta e grava o backend local. **Justificativa**: menor mudança de stack, preserva local-only e a experiência zero-config; llama.cpp pluga pelo provider `openai`+`base_url` sem código novo. **Trade-off**: throughput de embedding inferior a servidores com batching, dependência do cache. **Rejeitada**: TEI/vLLM (mais infra nova); substituir totalmente a auto-detecção (quebraria o deploy single-host). ([ADR-002](adrs/adr-002.md))
- **Decisão**: Fila PostgreSQL com `SKIP LOCKED` + workers separados. **Justificativa**: reuso do modelo/auditoria existentes, ACID, escala horizontal de escrita. **Trade-off**: migração de dados e novo processo. **Rejeitada**: Redis Streams (reescrita), SQLite (não escala). ([ADR-003](adrs/adr-003.md))
- **Decisão**: Reverse proxy na borda. **Justificativa**: LB + rate limit + sticky SSE simples em Swarm. **Trade-off**: afinidade reduz uniformidade de carga. **Rejeitada**: Kong/APISIX (peso operacional), middleware-only (não protege antes da app). ([ADR-004](adrs/adr-004.md))
- **Decisão**: Cache Redis de embedding + resultado. **Justificativa**: alavanca principal de latência com Ollama. **Trade-off**: risco de stale dentro do TTL. **Rejeitada**: só embedding (ganho parcial). ([ADR-005](adrs/adr-005.md))
- **Decisão**: Observabilidade Prometheus/Grafana + `/health`. **Justificativa**: necessária para provar a meta de p99. **Trade-off**: instrumentação adicional. **Rejeitada**: só logs (sem visibilidade de p99), +OpenTelemetry (peso no MVP).
- **Decisão**: Instalação via stack único + bootstrap script idempotente. **Justificativa**: preserva o requisito de instalação simplificada apesar dos muitos componentes; reproduzível e versionável. **Trade-off**: manter stack/script atualizados; migração de dados como passo guiado (não 100% automática). **Rejeitada**: wizard interativo (mais código), runbook manual (viola o requisito). ([ADR-006](adrs/adr-006.md))

### Riscos Conhecidos

- **Throughput de embedding sob cache frio em pico** (provável sob rajada simultânea): mitigar com réplicas de `ollama-embed` + TTL de embedding longo; monitorar hit rate. Pode exigir protótipo de carga.
- **Sticky sessions + MCP SSE através de proxy** (terreno pouco padronizado): validar no piloto a afinidade e a propagação de auth.
- **Invalidação de cache de busca incompleta**: mitigar com TTL curto (5 min) e métrica de stale; invalidação no ponto único pós-upsert.
- **Migração de dados SQLite → PostgreSQL sob uso**: janela planejada enquanto a base é pequena.

## Registros de Decisão de Arquitetura

- [ADR-001: Entrega integrada das Fases 0+1 com caminho de leitura priorizado](adrs/adr-001.md) — MVP único priorizando a leitura no rollout (decisão de produto, PRD).
- [ADR-002: Embedding e LLM como serviços Ollama dedicados e replicados via base_url](adrs/adr-002.md) — Reuso do provider Ollama sem código novo; cache como alavanca.
- [ADR-003: Fila durável em PostgreSQL com FOR UPDATE SKIP LOCKED e workers em processo separado](adrs/adr-003.md) — Dequeue seguro entre múltiplos workers; escala horizontal de escrita.
- [ADR-004: Borda via reverse proxy (Traefik/Nginx) com rate limit, circuit breaker e sticky sessions SSE](adrs/adr-004.md) — Proteção e LB simples em Swarm/VMs.
- [ADR-005: Cache Redis de embedding e de resultado de busca com invalidação por escrita](adrs/adr-005.md) — Latência sub-segundo no caminho quente.
- [ADR-006: Instalação automatizada via stack único + bootstrap script](adrs/adr-006.md) — Um comando provisiona todo o stack (DB, migrations, índices, config), preservando a instalação simplificada.
