# TechSpec — Prontidão para produção do OpenMemory (mem0-shared)

> Baseada no PRD `_prd.md` (Abordagem A — prontidão pragmática para LAN, 3 fases) e nos ADR-001 a ADR-006.

## Resumo Executivo

Este esforço endurece o OpenMemory para operação confiável em LAN single-node, **reusando ao máximo a infraestrutura existente** em vez de introduzir novos subsistemas. As decisões centrais: (1) um gate de CI que executa os 39 módulos de teste do `openmemory/api` via workflow reutilizável integrado ao `ci-gate.yml`; (2) backup/restauração e cold tier sobre **MinIO S3-compatível** usando snapshots nativos do Qdrant e `pg_dump`; (3) `max_memories` e cold tier como **novos job types no governance-worker existente**, sem serviço novo; (4) **OpenTelemetry** para tracing ponta a ponta + alertas Prometheus; (5) endurecimento proporcional ao risco LAN — API key por equipe, Docker secrets e rate limit por project+hostname via Redis.

**Principal trade-off técnico**: priorizamos reuso e baixo custo operacional (single-node, sem K8s/HA) em troca de **não ter alta disponibilidade** — a resiliência vem de backup/restauração testados e auto-recuperação de processos, não de redundância de nós. Enforcement de quota é assíncrono (pode exceder o teto transitoriamente) para não penalizar a latência de escrita.

## Arquitetura do Sistema

### Visão dos Componentes

**Fase 1 — Rede de segurança**
- **`openmemory-api-ci` (novo workflow CI)**: instala deps do `openmemory/api`, roda lint + `pytest`. Invocado pelo `ci-gate.yml` quando o PR toca `openmemory/api/**`. Relação: GitHub Actions → branch protection.
- **Serviço de backup (novo container/cron)**: dispara snapshot nativo do Qdrant + `pg_dump` do PostgreSQL e envia para bucket MinIO. Relação: Qdrant API de snapshots, PostgreSQL, MinIO.
- **MinIO (novo serviço)**: object store S3-compatível na LAN; destino de backups e snapshots de cold tier.

**Fase 2 — Qualidade + operabilidade**
- **Política de governança estendida**: `max_memories` + `max_memories_action` no resolver existente (`governance_policy.py`).
- **Job `enforce_quota` (novo handler)**: lê `memory_count` do catálogo `projects`; quarentena candidatos via `QuarantineEngine` até o teto (ação `enforce`) ou só alerta (ação `alert`).
- **Job `cold_tier` (novo handler)**: snapshot do escopo do project inativo para MinIO + remoção do acervo quente.
- **Instrumentação OTel**: spans na API e workers; exporta OTLP para **OpenTelemetry Collector** → **Tempo/Jaeger** (novos serviços no `compose/observability.yml`).
- **Regras de alerta Prometheus** + Alertmanager opcional.

**Fase 3 — Endurecimento leve**
- **Middleware de auth por equipe (novo)**: valida token por equipe contra mapa `team→token`; camada após `RequestIdMiddleware`.
- **Middleware de rate limit por project+hostname (novo)**: Redis sliding-window, reusa o Redis existente.
- **Docker secrets**: segredos saem do `.env` versionado.

**Fluxo de dados (inalterado no contrato MCP)**: clientes MCP → (auth + rate limit middlewares) → API → embed/Qdrant/fila → workers → Qdrant/PostgreSQL; tracing atravessa todo o caminho correlacionado por `request_id`/`job_id`.

## Design de Implementação

### Interfaces Principais

Como o repositório é Python, as "interfaces" são os contratos de handler e política existentes. O contrato a respeitar para os novos jobs de governança:

```python
# app/workers/governance_worker.py — assinatura de Handler já existente
Handler = Callable[..., int]  # handler(*, project: str | None, job_id: str, limit: int) -> int

# Novo handler de quota (app/governance/quota.py)
def run_enforce_quota_job(*, project: str, job_id: str, limit: int = 500) -> int:
    """Quarentena candidatos do project até memory_count <= max_memories.
    Ação 'alert' apenas emite métrica. Respeita pinned/protected. Retorna nº afetado."""

# Novo handler de cold tier (app/governance/cold_tier.py)
def run_cold_tier_job(*, project: str, job_id: str, limit: int = 500) -> int:
    """Se project inativo na janela: snapshot do escopo no MinIO + remove acervo quente.
    Reversível por restauração. Retorna nº de memórias arquivadas."""
```

Extensão da política (campos novos, mantendo o schema existente):

```python
# app/utils/governance_policy.py — adições a DEFAULT_POLICY / GovernancePolicySchema / EffectivePolicy
"max_memories": None,            # int | None  (None = sem teto)
"max_memories_action": "alert",  # "alert" | "enforce"
"cold_tier_idle_days": 180,      # inatividade que qualifica project p/ cold tier
```

### Modelos de Dados

- **`GovernanceJobType` (enum)**: adicionar `enforce_quota`, `cold_tier`. Requer migration se o backend materializa o enum.
- **`Project` (existente)**: reusar `memory_count`; adicionar coluna opcional `last_activity_at` (datetime) para janela de inatividade do cold tier, alimentada pelo write path / access logs.
- **`SCHEDULE_INTERVALS`**: adicionar `monthly: timedelta(days=30)`.
- **Backups (objetos no MinIO)**: convenção de chave `backups/{yyyy-mm-dd}/qdrant/{collection}.snapshot` e `backups/{yyyy-mm-dd}/postgres/dump.sql.gz`; cold tier em `cold/{project}/{timestamp}.snapshot`.
- **Sem novas tabelas** para auth: o mapa `team→token` vem de secret/config, não de banco.

### Endpoints de API

Estendem os routers `admin`/`governance` existentes:

| Método | Caminho | Descrição |
|--------|---------|-----------|
| POST | `/admin/backup/run` | Dispara backup sob demanda (Qdrant + PG → MinIO); retorna `job_id`/chave |
| POST | `/admin/backup/restore` | Inicia restauração a partir de uma chave de backup (202) |
| GET | `/admin/backup/status` | Último backup, tamanho, timestamp, RPO corrente |
| PUT | `/admin/governance/policies` | (existente) passa a aceitar `max_memories`, `max_memories_action`, `cold_tier_idle_days` |
| POST | `/admin/governance/jobs/enforce_quota` | (via rota genérica existente) enfileira manualmente |
| POST | `/admin/governance/jobs/cold_tier` | idem |

Auth/rate limit são transversais (middleware), não endpoints.

## Pontos de Integração

- **MinIO (S3-compatível)**: cliente via `boto3`/`mc`; auth por access key/secret em Docker secret; retry com backoff em uploads; destino configurável por `S3_ENDPOINT`/`S3_BUCKET`.
- **Qdrant Snapshots API**: criar/baixar snapshot por coleção; tratar falha como job retryável.
- **OpenTelemetry Collector**: exportação OTLP/gRPC assíncrona; sampling configurável; falha de export não pode quebrar request (degradação graciosa).

## Análise de Impacto

| Componente | Tipo de Impacto | Descrição e Risco | Ação Necessária |
|------------|-----------------|-------------------|-----------------|
| `.github/workflows/ci-gate.yml` | modificado | Novo filtro + call job + needs. Risco baixo | Adicionar `openmemory_api` |
| `.github/workflows/openmemory-api-ci.yml` | novo | Pipeline de testes do api. Risco baixo | Criar workflow reutilizável |
| `compose/*` + `docker-compose.scale.yml` | modificado | MinIO, Collector, Tempo/Jaeger, serviço de backup. Risco médio (mais serviços) | Adicionar serviços e secrets |
| `app/utils/governance_policy.py` | modificado | Novos campos de política. Risco baixo (compatível) | Estender schema/default |
| `app/workers/governance_worker.py` | modificado | Registrar handlers + `monthly`. Risco baixo | Dispatcher + intervals |
| `app/governance/quota.py`, `cold_tier.py` | novo | Lógica de enforce/arquivamento. Risco médio (poda de dados) | Implementar + testes |
| `app/models.py` | modificado | Enum job types + `Project.last_activity_at`. Risco médio (migration) | Migration Alembic |
| `app/middleware/*` | novo | Auth por equipe + rate limit Redis. Risco médio (pode bloquear clientes) | Modo warn → enforce |
| `app/utils/metrics.py` | modificado | Métricas de quota/cold-tier/backup. Risco baixo | Novos coletores |
| `app/routers/admin.py` | modificado | Endpoints de backup. Risco baixo | Novas rotas |

## Abordagem de Testes

### Testes Unitários
- `enforce_quota`: seleção de candidatos respeita pinned/protected; ação `alert` não remove; `enforce` reduz até o teto; mock de `QuarantineEngine` e catálogo.
- `cold_tier`: detecta inatividade pela janela; chama snapshot e remoção; idempotência; mock do cliente MinIO e Qdrant.
- Política: merge de `max_memories`/ação global × override; validação de valores.
- Middlewares: token válido/ inválido/ ausente (modo warn vs enforce); rate limit estoura e libera após janela (mock Redis).
- Backup/restore: orquestração com mocks de Qdrant snapshot, `pg_dump` e MinIO; geração de chave; status/RPO.

### Testes de Integração
- CI: o próprio `openmemory-api-ci` rodando `pytest openmemory/api/tests` é o teste de integração do gate (services Qdrant/Postgres quando necessário).
- Backup→restore end-to-end contra MinIO e Qdrant/Postgres efêmeros (drill automatizável).
- Tracing: asserir que um request gera spans encadeados (exporter em memória).

## Sequenciamento de Desenvolvimento

### Ordem de Construção
1. **Gate de CI** (`openmemory-api-ci.yml` + wiring no `ci-gate.yml`) — sem dependências. Entrega a rede de segurança antes de qualquer mudança de código.
2. **MinIO + serviço de backup + endpoints `/admin/backup/*`** — depende do passo 1 (para validar via CI). Inclui drill de restauração.
3. **Migration de modelos** (enum `enforce_quota`/`cold_tier`, `Project.last_activity_at`, `monthly`) — depende do passo 1.
4. **Política estendida** (`max_memories`, ação, `cold_tier_idle_days`) — depende do passo 3.
5. **Handler `enforce_quota`** + registro no dispatcher + métricas — depende dos passos 3 e 4.
6. **Handler `cold_tier`** + registro + métricas — depende dos passos 2 (MinIO/snapshot) e 4.
7. **Instrumentação OTel + Collector + backend de traces** — depende do passo 1; independe dos jobs.
8. **Regras de alerta Prometheus** — depende do passo 7 e das métricas dos passos 5–6.
9. **Middleware de rate limit por project+hostname** — depende do passo 1; reusa Redis.
10. **Middleware de auth por equipe + Docker secrets** (modo warn → enforce) — depende do passo 9 (ordenação de middlewares) e do passo 2 (secrets).

### Dependências Técnicas
- MinIO provisionado na LAN (ou S3 externo acessível) antes dos passos 2 e 6.
- Redis já existente (rate limit) — sem nova infra.
- Versões de pacotes OTel compatíveis com a versão do FastAPI/SQLAlchemy do projeto.

## Monitoramento e Observabilidade

- **Métricas novas**: `governance_quota_enforced_total`, `governance_quota_over_limit_projects`, `governance_cold_tier_archived_total`, `backup_last_success_timestamp`, `backup_duration_seconds`, `backup_age_seconds` (para RPO).
- **Traces**: spans `mcp.search`, `embed`, `qdrant.search`, `llm.extract`, `write.enqueue/dequeue`, correlacionados por `request_id`/`job_id`.
- **Alertas (limiares iniciais)**: `mcp_search_latency_p99 > 500ms`; `write_queue_depth` crescente sustentado; `governance_job_errors_total` > 0 em janela; `backup_age_seconds > 24h` (RPO violado); `project_size_over_threshold > 0`.
- **Logs**: manter estruturado; incluir `trace_id` nos campos para pivô log↔trace.

## Considerações Técnicas

### Decisões-Chave
- **Reuso do governance-worker para quota/cold-tier** (ADR-005): justificativa — fila/scheduler/quarantine já existem; trade-off — enforcement assíncrono; alternativa rejeitada — microserviço dedicado.
- **MinIO + snapshots nativos** (ADR-003): justificativa — backup sobrevive à falha do nó e cold tier reusa o mesmo mecanismo; trade-off — um serviço a mais; alternativa rejeitada — volume local e dump via scroll.
- **CI gate via workflow reutilizável** (ADR-002): justificativa — único status check requerido; alternativa rejeitada — workflow standalone não-gated.
- **OTel self-hosted** (ADR-004): justificativa — padrão portável sem enviar dados para fora; alternativa rejeitada — APM SaaS.
- **Endurecimento proporcional** (ADR-006): justificativa — LAN confiável dispensa mTLS/JWT; alternativa adiada — mTLS/Vault.

### Riscos Conhecidos
- **Poda de dados por quota/cold-tier**: risco de remover memória útil. Mitigação: default `alert`, reversibilidade por quarentena, respeito a pinned/protected, snapshot antes de remover.
- **Testes que exigem serviços no CI**: alguns podem precisar de Qdrant/Postgres. Mitigação: `services:` no job ou isolar com mocks/SQLite.
- **Overhead de tracing em volume**: mitigação por sampling e export assíncrono.
- **Virada de auth para obrigatório quebrar clientes**: mitigação por modo warn + comunicação.

## Registros de Decisão de Arquitetura

- [ADR-001: Prontidão para produção orientada ao alvo LAN interna](adrs/adr-001.md) — Abordagem A faseada, adiando HA/K8s/coleção-por-project.
- [ADR-002: Gate de CI para o openmemory/api via workflow reutilizável no CI Gate](adrs/adr-002.md) — Testes do api passam a barrar merges.
- [ADR-003: Backup/restauração e cold tier sobre MinIO (S3-compatível) com snapshots nativos](adrs/adr-003.md) — Object store desacoplado do nó.
- [ADR-004: Observabilidade — tracing distribuído com OpenTelemetry e alertas Prometheus](adrs/adr-004.md) — Diagnóstico ponta a ponta self-hosted.
- [ADR-005: max_memories e cold tier como job types no governance-worker existente](adrs/adr-005.md) — Reuso da infraestrutura de governança.
- [ADR-006: Endurecimento para LAN — API key por equipe, secrets gerenciados e rate limit por project](adrs/adr-006.md) — Segurança proporcional ao risco LAN.
