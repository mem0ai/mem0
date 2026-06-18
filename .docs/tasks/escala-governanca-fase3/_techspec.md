# TechSpec — Fase 3: Governança de qualidade da memória

> **Idioma:** PT-BR. **Status:** rascunho para revisão. **Data:** 2026-06-18.
> **Entrada:** [_prd.md](_prd.md) (Fase 3). **Decisões:** [ADR-001](adrs/adr-001.md), [ADR-002](adrs/adr-002.md), [ADR-003](adrs/adr-003.md), [ADR-004](adrs/adr-004.md), [ADR-005](adrs/adr-005.md).

## Resumo Executivo

A Fase 3 adiciona uma **suíte de governança de qualidade** sobre a fundação das Fases 0–2, sem tocar no contrato MCP (`search_memory`, `add_memories`). Um novo serviço **`governance-worker`** (mesmo padrão do `migration_worker` da Fase 2) agenda e executa, fora de pico, jobs idempotentes sobre a fila PostgreSQL: **dedup**, **poda por TTL** (idade **e** último acesso), **consolidação semântica** (merge de quase-duplicatas + resolução de contradições) e **purge**. Toda ação destrutiva passa por uma **rede de segurança**: um novo estado `quarantined` que **preserva o vetor no Qdrant** e exclui a memória da busca por filtro implícito, com **reversão barata** e **expurgo diferido** após janela configurável; memórias pinadas (`metadata.pinned`) são imunes. A consolidação semântica gera candidatos por similaridade vetorial (barato, recall) e adjudica com o **LLM Service** (preciso) para merge/contradição. As políticas seguem o modelo **global (`Config`) + override por projeto** (`governance_policies`), e a qualidade é medida por **métricas-proxy contínuas** mais uma **avaliação periódica com LLM-juiz**.

**Trade-off técnico principal:** trocamos simplicidade por uma rede de segurança que custa **armazenamento extra** (vetores em quarentena durante a janela) e um **filtro implícito `state=active` em toda busca** — em troca de automação destrutiva **reversível e auditável**, segura o bastante para operar em escala sem aprovação manual item a item. Em segundo plano, a consolidação semântica aceita **custo e não-determinismo de LLM** (mitigados por pré-filtragem vetorial, execução em lote fora de pico e alerta por taxa de reversão) em favor da qualidade real de merge/contradição.

## Arquitetura do Sistema

### Visão dos Componentes

- **`governance-worker` (`openmemory/api/app/workers/governance_worker.py`)** — *novo*. Serviço dedicado. Papel **agendador** (`replicas: 1`): loop temporal que, conforme a política efetiva, enfileira `GovernanceJob` (`dedup`, `ttl_prune`, `consolidate`, `purge`) na fila PostgreSQL. Papel **processador**: consome a fila (`FOR UPDATE SKIP LOCKED`), executando jobs idempotentes com retomada e backoff, reaproveitando a estrutura de `WriteWorker`/`WriteQueue` (ADR-002).
- **Fila de governança (`openmemory/api/app/utils/governance_queue.py`)** — *novo*. Espelha `write_queue.py`: enqueue/dequeue de `GovernanceJob` em `governance_jobs`.
- **Motor de quarentena/lifecycle (`openmemory/api/app/utils/quarantine.py`)** — *novo helper*. Encapsula as transições de/para `quarantined` (SQL + payload Qdrant + `MemoryStatusHistory`), reversão e expurgo, com proteção de pinadas (ADR-003).
- **Resolvedor de política (`openmemory/api/app/utils/governance_policy.py`)** — *novo helper*. `resolve_policy(project) -> EffectivePolicy` por *merge* de `Config(key="governance")` global com override de `governance_policies` (ADR-005).
- **Pipeline de consolidação (`openmemory/api/app/governance/consolidation.py`)** — *novo*. Geração de candidatos via Qdrant (`search_batch` por `project`+`type`) + adjudicação por LLM (cliente reutilizado de `config.py`), produzindo ações merge/contradição/none (ADR-004).
- **Provider Qdrant (`mem0/vector_stores/qdrant.py`)** — *modificado*. Índice de payload `state` (keyword); filtro de busca passa a incluir `state="active"` implicitamente; expõe hard-delete já existente (`delete`) para o purge.
- **Camada de busca (`mcp_server.py`, `routers/compat_v3.py`, `utils/memory.py`)** — *modificado minimamente*. Injeta o filtro `state="active"` na montagem de filtros; **contrato MCP inalterado**.
- **Modelos + Alembic (`openmemory/api/app/models.py`)** — *novo/modificado*. Enum `MemoryState` + `quarantined`; coluna `quarantined_at`; tabelas `governance_jobs`, `governance_policies`, `governance_schedule`; reuso de `MemoryStatusHistory`.
- **API de operação (`routers/admin.py`, `routers/config.py`)** — *modificado*. Endpoints `/admin/governance/*` (enfileirar jobs, auditar, reverter, políticas).
- **Métricas (`utils/metrics.py`) + LLM-juiz (`governance/quality_eval.py`)** — *modificado/novo*. Contadores/gauges de governança + job periódico de aferição de qualidade.

### Fluxo de dados

- **Agendamento → execução:** `governance-worker` (agendador) lê `governance_schedule` + política efetiva → enfileira `GovernanceJob` → `governance-worker` (processador) consome → aplica dedup/TTL/consolidação → transições de estado via motor de quarentena → audit em `MemoryStatusHistory` → métricas.
- **Quarentena:** memória alvo → `state=quarantined` (SQL: `quarantined_at`, `metadata_`; Qdrant: payload `state="quarantined"`, **vetor mantido**) → excluída da busca por filtro.
- **Reversão:** `quarantined → active` (SQL + payload); vetor nunca saiu → operação barata.
- **Expurgo:** job `purge` seleciona `quarantined` com `quarantined_at` além da janela → `vector_store.delete` (hard) + linha SQL → único passo irreversível.
- **Leitura (inalterada para o dev):** MCP → filtros `{project, ..., state="active"}` → Qdrant (coleção ativa resolvida pela Fase 2).

## Design de Implementação

### Interfaces Principais

Tipo central que o worker e os endpoints consomem para a política efetiva de um projeto (Python, alinhado ao stack do repositório):

```python
# openmemory/api/app/utils/governance_policy.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class EffectivePolicy:
    ttl_max_age_days: int            # poda por idade
    ttl_idle_days: int               # poda por tempo desde o último acesso
    quarantine_window_days: int      # janela reversível antes do expurgo
    consolidation_enabled: bool      # liga o Incremento 2 (merge/contradição)
    similarity_threshold: float      # candidatura de quase-duplicatas (ex.: 0.9)
    contradiction_tiebreak: str      # "recency" | "confidence"
    protected_categories: tuple[str, ...] = field(default_factory=tuple)  # pinadas por padrão
    schedules: dict = field(default_factory=dict)  # {"dedup":"daily","consolidate":"weekly",...}

def resolve_policy(project: str) -> EffectivePolicy:
    """Merge de Config(key='governance') global com override de governance_policies."""
    ...
```

Contrato do motor de quarentena, ponto único de toda transição destrutiva reversível (ADR-003):

```python
# openmemory/api/app/utils/quarantine.py
from uuid import UUID

class QuarantineEngine:
    """Transições de/para 'quarantined' em SQL + payload Qdrant + audit. Protege pinadas."""
    def quarantine(self, memory_id: UUID, *, reason: str, job_id: str) -> bool: ...   # False se pinada
    def revert(self, memory_id: UUID) -> None: ...                                    # quarantined -> active
    def purge_expired(self, *, older_than_days: int, limit: int) -> int: ...          # hard-delete pós-janela
```

**Tratamento de erros:** jobs são idempotentes por `memory_id`/`point_id`; falhas isoladas não abortam o lote (registradas em log estruturado + contador de erro) e o job é reenfileirado com backoff até `max_attempts`. A adjudicação por LLM que falha trata o candidato como `none` (não age) — falha segura. O motor de quarentena nunca toca memórias com `metadata.pinned == true`.

### Modelos de Dados

Enum `MemoryState` (modificado) e coluna nova em `memories`:

| Mudança | Detalhe |
|---------|---------|
| `MemoryState.quarantined` | Novo valor do enum (governança); distinto de `archived` (usuário) e `deleted` |
| `memories.quarantined_at` | `DateTime`, nullable, index — início da janela de quarentena |

Nova tabela `governance_jobs` (fila; espelha `write_queue_jobs`):

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID (PK) | Identificador do job |
| `job_type` | enum | `dedup`, `ttl_prune`, `consolidate`, `purge` |
| `project` | text (nullable) | Escopo (projeto) ou global |
| `status` | enum | `queued`, `processing`, `done`, `failed` |
| `attempts` | int | Tentativas (backoff) |
| `payload` | JSON | Parâmetros/checkpoint do job |
| `created_at` / `updated_at` | datetime | Timestamps |

Nova tabela `governance_policies` (override por projeto; ADR-005):

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `project_name` | text (PK, FK → `projects.name`) | Projeto com política divergente |
| `overrides` | JSON | Campos que sobrescrevem o global (parcial) |
| `updated_at` | datetime | Última atualização |

Nova tabela `governance_schedule` (idempotência da agenda):

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_type` | enum (PK) | Tipo de job agendado |
| `scope` | text (PK) | Projeto ou `__global__` |
| `last_run_at` | datetime | Última execução agendada |

Política global: documento `Config(key="governance")` (JSON) com os mesmos campos de `EffectivePolicy`. **Payload Qdrant:** acrescenta/indexa `state` (keyword); demais campos inalterados.

### Endpoints de API

Operacionais (operador/painel), sob o prefixo administrativo existente:

| Método | Caminho | Descrição |
|--------|---------|-----------|
| GET | `/admin/governance/policies` | Retorna política global + overrides por projeto |
| PUT | `/admin/governance/policies` | Atualiza política global (`Config`) |
| PUT | `/admin/governance/policies/{project}` | Cria/atualiza override do projeto |
| POST | `/admin/governance/jobs/{type}` | Enfileira job (`dedup`/`ttl_prune`/`consolidate`/`purge`), escopo opcional por projeto |
| GET | `/admin/governance/audit` | Lista ações de governança (filtra por projeto/tipo/período via `MemoryStatusHistory`) |
| POST | `/admin/governance/revert/{memory_id}` | Reverte memória de `quarantined` para `active` |
| GET | `/admin/governance/quality` | Último índice de qualidade (proxy + LLM-juiz) |

Contrato MCP (`search_memory`, `add_memories`) e `compat_v3` permanecem **sem alteração de assinatura** — o filtro `state="active"` é interno.

## Pontos de Integração

- **LLM Service (Fase 1)** — adjudicação de merge/contradição (ADR-004) e LLM-juiz da aferição de qualidade. Cliente/credenciais reutilizados de `routers/config.py`. Chamadas em **lote, fora de pico**; falha → ação `none` (segura) + retry com backoff.
- **Cluster Qdrant (Fase 2)** — candidatura por `search_batch` (escopo `project`+`type`), atualização de payload `state`, hard-delete no purge. Idempotência por `point_id`.
- **PostgreSQL/PgBouncer (Fase 0+1)** — fonte de verdade de fila, políticas, agenda e audit.
- **Prometheus (existente)** — exposição das novas métricas via `/metrics`.

## Análise de Impacto

| Componente | Tipo de Impacto | Descrição e Risco | Ação Necessária |
|------------|-----------------|-------------------|-----------------|
| `models.py` + Alembic | novo/modificado | `quarantined` no enum + `quarantined_at`; tabelas `governance_jobs`/`governance_policies`/`governance_schedule`. Risco baixo. | Migrations; backfill de índice de payload `state`. |
| `mem0/vector_stores/qdrant.py` | modificado | Índice de payload `state` + filtro implícito `state="active"` na busca. Risco médio (caminho crítico de leitura). | Estender montagem de filtro; testes de regressão. |
| `mcp_server.py`, `compat_v3.py`, `utils/memory.py` | modificado | Injetar `state="active"` nos filtros. Risco médio (não regredir resultados). | Ponto único de filtro + testes. |
| `workers/governance_worker.py` | novo | Agendador + processador de jobs. Risco médio (automação destrutiva). | Implementar com idempotência/backoff e singleton de agenda. |
| `utils/quarantine.py` | novo | Transições reversíveis + expurgo + proteção de pinadas. Risco alto (perda de dados). | Cobertura de testes forte; auditoria. |
| `governance/consolidation.py` | novo | Candidatura vetorial + adjudicação LLM. Risco alto (merge incorreto). | Limiares conservadores; alerta de taxa de reversão. |
| `utils/governance_policy.py` | novo | Merge global+override. Risco baixo. | Validação Pydantic + defaults. |
| `routers/admin.py`, `routers/config.py` | modificado | Endpoints `/admin/governance/*`. Risco baixo. | Seguir padrão existente. |
| `utils/metrics.py` + `governance/quality_eval.py` | modificado/novo | Métricas de governança + LLM-juiz. Risco baixo. | Registrar métricas; job de aferição. |
| Deploy (Swarm) | novo | Serviço `governance-worker` (agendador `replicas:1`). Risco médio (infra/singleton). | Adicionar ao `docker-stack.yml`. |

## Abordagem de Testes

### Testes Unitários

- **`QuarantineEngine`**: `quarantine` ignora pinadas (retorna `False`); grava `quarantined_at`, payload e `MemoryStatusHistory`; `revert` restaura `active` sem reembedar; `purge_expired` só atinge `quarantined` além da janela.
- **`resolve_policy`**: merge correto (override sobrepõe global; campos ausentes herdam; defaults conservadores quando faltam no global).
- **Filtro de busca**: `state="active"` sempre presente; memórias `quarantined`/`deleted` nunca retornam; cross-project e filtros de projeto continuam corretos (regressão).
- **Candidatura de consolidação**: respeita `project`+`type` e limiar; exclui `state != active` e pinadas.
- **Adjudicação LLM (mock)**: merge produz canônica + quarentena das fontes; contradição aplica desempate; `none` não altera nada; falha de LLM → `none`.
- **Fila/idempotência**: `governance_queue` dequeue com `SKIP LOCKED`; reprocessamento de job é idempotente; backoff até `max_attempts`.
- **Agenda**: agendador só enfileira jobs "vencidos" por `governance_schedule`; não duplica em execução repetida.

### Testes de Integração

- **Ciclo de quarentena ponta a ponta** (Qdrant + PG de teste): poda por TTL → memória some da busca, vetor permanece no Qdrant → `revert` → memória volta à busca → após janela, `purge` remove definitivamente.
- **Consolidação semântica** (LLM mock/fixture): popular quase-duplicatas e um par contraditório → rodar `consolidate` → canônica presente, fontes em quarentena, contraditória perdedora quarentenada; pinadas intactas.
- **Não-regressão de leitura**: conjunto de buscas (projeto e cross-project) retorna o mesmo conteúdo `active` antes/depois de ativar o filtro de estado.
- **Proteção de pinadas**: memória pinada candidata a dedup/TTL/merge nunca é tocada por nenhum job.
- **Aferição de qualidade**: proxy (quase-duplicatas no top-K) cai após consolidação; LLM-juiz (mock) gera índice; endpoint `/admin/governance/quality` reflete os valores.
- **Ambiente:** Qdrant + PostgreSQL de teste; dataset sintético com duplicatas exatas, quase-duplicatas, contradições, memórias antigas/ociosas e pinadas.

## Sequenciamento de Desenvolvimento

### Ordem de Construção

1. **Modelos + migrations** (`quarantined` no enum, `quarantined_at`, tabelas `governance_jobs`/`governance_policies`/`governance_schedule`, índice de payload `state`) — sem dependências.
2. **Resolvedor de política** (`resolve_policy` + validação Pydantic + `Config(key="governance")`) — depende do passo 1.
3. **Filtro de estado na busca** (`state="active"` em `qdrant.py` + camada MCP/compat_v3) — depende do passo 1; entregar cedo para garantir não-regressão.
4. **`QuarantineEngine`** (transições reversíveis + proteção de pinadas + audit) — depende dos passos 1 e 3.
5. **Fila + esqueleto do `governance-worker`** (`governance_queue`, dequeue `SKIP LOCKED`, loop processador, idempotência/backoff) — depende do passo 1.
6. **Agendador interno** (loop temporal + `governance_schedule`, singleton) — depende dos passos 2 e 5.
7. **Job de dedup em lote** (consolidar duplicatas exatas por hash → quarentena) — depende dos passos 4, 5.
8. **Job de poda por TTL** (idade **e** último acesso → quarentena) — depende dos passos 2, 4, 5.
9. **Job de purge** (`purge_expired` pós-janela) — depende dos passos 4, 5.
10. **Pipeline de consolidação semântica** (candidatura Qdrant + adjudicação LLM → merge/contradição) — depende dos passos 4, 5 e do LLM Service; ativado após validação dos passos 7–9 (faseamento do ADR-001).
11. **Endpoints `/admin/governance/*`** (políticas, enfileirar, audit, revert, quality) — depende dos passos 2, 4, 5.
12. **Métricas + LLM-juiz** (`utils/metrics.py` + `quality_eval.py` + endpoint quality) — depende dos passos 7–10.
13. **Deploy** (serviço `governance-worker` no `docker-stack.yml`, agendador `replicas:1`) — depende dos passos 6–10.

### Dependências Técnicas

- **Migração de enum/coluna no PostgreSQL** e **índice de payload `state` no Qdrant** (backfill na base existente) — bloqueia passos 3, 4, 7–10.
- **LLM Service (Fase 1) disponível e dimensionado** para lotes de adjudicação fora de pico — bloqueia passos 10 e 12 (LLM-juiz).
- **Cluster Qdrant (Fase 2)** com `search_batch` e o resolvedor de coleção ativa — bloqueia candidatura e busca.
- **Definição dos defaults conservadores** da política global (janela de quarentena, idade/uso de poda, limiar de similaridade) — pergunta em aberto do PRD; bloqueia ativação real, não a implementação.

## Monitoramento e Observabilidade

- **Métricas (Prometheus):**
  - `governance_job_queue_depth{job_type}` (gauge), `governance_job_latency_seconds{job_type}` (histogram), `governance_job_errors_total{job_type}` (counter).
  - `governance_deduped_total`, `governance_pruned_total`, `governance_merged_total`, `governance_contradictions_resolved_total`, `governance_purged_total`, `governance_reverted_total` (counters).
  - `governance_quarantined_current` (gauge), `governance_revert_rate{job_type}` (gauge — gatilho de alerta), `retrieval_duplicate_in_topk_ratio` (gauge — proxy de qualidade), `retrieval_quality_index` (gauge — LLM-juiz periódico).
- **Logs estruturados:** evento por ação (`quarantine`/`revert`/`purge`/`merge`/`contradiction`) com `memory_id`, `job_id`, `job_type`, `project`, `reason`; eventos de agenda (`scheduled`/`enqueued`) com `scope`.
- **Alertas:** `governance_revert_rate` (merge/contradição) acima do limiar → pausar Incremento 2; `governance_job_errors_total` > 0 sustentado; `governance_job_queue_depth` crescente (agendador parado); `retrieval_quality_index` em queda.

## Considerações Técnicas

### Decisões-Chave

- **Decisão:** `governance-worker` dedicado com loop temporal interno sobre fila PostgreSQL. **Justificativa:** zero dependências novas, reusa o padrão fila+worker, agenda e execução versionadas. **Trade-offs:** agendador como singleton (`replicas:1`); loop simples sem cron expressions. **Alternativas rejeitadas:** cron externo, APScheduler, estender write_worker ([ADR-002](adrs/adr-002.md)).
- **Decisão:** estado `quarantined` dedicado, vetor retido, expurgo diferido. **Justificativa:** reversão barata e auditável sem conflitar com `archived`/`deleted`. **Trade-offs:** filtro implícito `state="active"` em toda busca + armazenamento extra na janela. **Alternativas rejeitadas:** reusar `archived`/`deleted`, backup externo ([ADR-003](adrs/adr-003.md)).
- **Decisão:** consolidação = candidatura por vetor + adjudicação por LLM. **Justificativa:** qualidade real de merge/contradição com custo de LLM controlado. **Trade-offs:** custo e não-determinismo de LLM. **Alternativas rejeitadas:** só heurística vetorial, reusar `add()` ([ADR-004](adrs/adr-004.md)).
- **Decisão:** política global (`Config`) + override por projeto (`governance_policies`). **Justificativa:** padrão simples de manter, overrides esparsos e auditáveis. **Trade-offs:** lógica de merge e validação na aplicação. **Alternativas rejeitadas:** estender `ArchivePolicy`, colunas em `projects`, tudo em um JSON ([ADR-005](adrs/adr-005.md)).
- **Decisão:** medição de qualidade por proxy contínuo + LLM-juiz periódico. **Justificativa:** sinal barato e contínuo no dia a dia, aferição fiel periódica como referência. **Trade-offs:** proxy é aproximação; LLM-juiz custa inferência.

### Riscos Conhecidos

- **Merge/contradição incorretos pelo LLM** (média): limiar conservador na candidatura, prompt exigindo equivalência forte, quarentena (não exclusão), alerta por taxa de reversão como gatilho de pausa.
- **Vazamento de memória quarentenada para a busca** (média): filtro `state="active"` num ponto único + testes de regressão; entregar o filtro cedo (passo 3).
- **Poda agressiva** (média): TTL por idade **e** último acesso, padrões conservadores por projeto, quarentena reversível, proteção de pinadas.
- **Execução dupla de jobs** (baixa, mitigada): agendador singleton + idempotência por `governance_schedule` e `SKIP LOCKED`.
- **Custo de LLM em base grande** (média): processamento por projeto/lote com teto, fora de pico; candidatura vetorial limita chamadas.
- **Migração de enum/backfill de `state` na base viva** (média): aplicar índice de payload e backfill em background; default `active` para pontos sem `state`.

## Registros de Decisão de Arquitetura

- [ADR-001: Governança de qualidade automática com rede de segurança, faseada](adrs/adr-001.md) — Automação destrutiva reversível (soft-delete + proteção de pinadas), em dois incrementos (guarda-corpos antes da consolidação semântica). *(decisão de produto, herdada do PRD)*
- [ADR-002: Worker de governança dedicado com loop temporal interno sobre fila PostgreSQL](adrs/adr-002.md) — Agendar e executar os jobs num serviço dedicado reusando o padrão fila+worker, sem dependências novas.
- [ADR-003: Estado `quarantined` dedicado com retenção do vetor e expurgo diferido](adrs/adr-003.md) — Novo estado de governança que preserva o vetor para reversão barata e isola o expurgo irreversível num job próprio.
- [ADR-004: Consolidação semântica por candidatura via vetor + adjudicação por LLM](adrs/adr-004.md) — Gerar candidatos por similaridade vetorial e decidir merge/contradição com o LLM Service, em lote e fora de pico.
- [ADR-005: Políticas de governança — Config JSON global + tabela de override por projeto](adrs/adr-005.md) — Padrão global em `Config` e overrides esparsos por projeto numa tabela dedicada, resolvidos por merge.
