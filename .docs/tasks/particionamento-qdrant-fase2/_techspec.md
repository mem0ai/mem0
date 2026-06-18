# TechSpec — Fase 2: Particionamento e escala de armazenamento da memória

> **Idioma:** PT-BR. **Status:** rascunho para revisão. **Data:** 2026-06-17.
> **Entrada:** [_prd.md](_prd.md) (Fase 2). **Decisões:** [ADR-001](adrs/adr-001.md), [ADR-002](adrs/adr-002.md), [ADR-003](adrs/adr-003.md).

## Resumo Executivo

A Fase 2 transforma o armazenamento vetorial de **uma coleção single-node sem índice de projeto** em uma **coleção particionada por inquilino sobre cluster Qdrant**, preservando o contrato MCP existente. O projeto vira uma chave de inquilino indexada (`is_tenant=true`), co-localizando fisicamente os pontos de cada projeto para manter a latência de busca plana mesmo com o crescimento do volume; projetos "gigantes" são promovidos a `shard_key` dedicado sob demanda (ADR-002). A base existente é migrada por uma estratégia **blue-green** conduzida por um **worker de migração dedicado** com estado em PostgreSQL — cópia em background com checkpoint, dual-write durante a janela, validação e flip atômico do ponteiro de coleção ativa, com a coleção antiga mantida para reversão (ADR-003).

**Trade-off técnico principal:** trocamos isolamento físico por projeto (coleção dedicada) por isolamento **lógico** na coleção compartilhada — isso mantém a busca cross-project barata (caso de uso comum) e a latência plana, ao custo de aceitar que um incidente de infraestrutura na coleção compartilhada possa afetar mais de um projeto, mitigado por replicação (RF=2) e pela promoção de gigantes a shard keys dedicados. Em segundo plano, a janela de migração incorre em escrita e armazenamento duplicados temporários, em troca de zero downtime e reversibilidade.

## Arquitetura do Sistema

### Visão dos Componentes

- **Provider Qdrant (`mem0/vector_stores/qdrant.py`)** — *modificado*. Passa a criar índice de payload de inquilino para `project` (`is_tenant=true`) e índices adicionais (`type`, `created_at`, `hash`); suporta criação de coleção com `shard_number`/`replication_factor`/`sharding_method=CUSTOM` e `shard_key_selector` em busca/escrita escopada a projeto promovido.
- **Resolvedor de coleção ativa (`openmemory/api/app/utils/memory.py`)** — *novo helper*. Resolve o nome da coleção a partir de `migration_state.active_collection` (com cache em memória + invalidação no flip), substituindo o `collection_name` fixo `"openmemory"`. Usado pela API e pelos workers.
- **Worker de migração (`openmemory/api/app/workers/migration_worker.py`)** — *novo*. Deployment separado. Executa: (a) provisão da coleção green; (b) cópia blue→green por `scroll`+`upsert` com checkpoint; (c) validação; (d) flip; (e) promoção de projeto gigante (reescrita com `shard_key`). Estado em PostgreSQL.
- **Write-worker (`workers/write_worker.py`)** — *modificado*. Quando `dual_write_enabled`, grava também na coleção destino após o `add` normal. Lê a coleção ativa pelo resolvedor.
- **API MCP / compat_v3 (`mcp_server.py`, `routers/compat_v3.py`)** — *modificado minimamente*. Continua montando o filtro `{"project": ...}`; passa a obter a coleção ativa via resolvedor. Contrato das ferramentas (`search_memory`, `add_memories`) inalterado.
- **Estado em PostgreSQL** — *novo/estendido*. Tabela `migration_state` (progresso global) + colunas `partition_tier`/`shard_key` em `projects`. Endpoint operacional de tamanho/saúde por projeto.

### Fluxo de dados

- **Leitura:** MCP → resolvedor de coleção ativa → cache de embedding/resultado (Fase 1) → `vector_store.search(filters={"project"}, [shard_key_selector se promovido])` na coleção ativa.
- **Escrita:** MCP enfileira → write-worker processa `add` na coleção ativa → se `dual_write_enabled`, replica na coleção destino → cataloga/atualiza `projects.memory_count`.
- **Migração:** migration_worker lê blue por `scroll` (cursor em `migration_state`) → `upsert` em green → valida → flip de `active_collection`.

## Design de Implementação

### Interfaces Principais

Tipo central que os demais componentes consomem para resolver a coleção ativa e o roteamento de shard (Python, alinhado ao stack do repositório):

```python
# openmemory/api/app/utils/partitioning.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class CollectionRoute:
    collection: str                  # coleção ativa resolvida (blue ou green)
    shard_key: Optional[str] = None  # definido só para projeto promovido (tier=dedicated)

class PartitionResolver:
    """Resolve a coleção ativa e o shard_key por projeto a partir do estado em PostgreSQL.
    Mantém cache em memória invalidado no flip e na promoção."""
    def route_for(self, project: str) -> CollectionRoute: ...
    def active_collection(self) -> str: ...
    def invalidate(self) -> None: ...   # chamado no flip de coleção e na promoção
```

Extensão do provider para o índice de inquilino (assinatura afetada):

```python
# mem0/vector_stores/qdrant.py — Qdrant._create_filter_indexes (modificado)
# project como índice de inquilino; demais campos conforme proposta técnica.
TENANT_FIELD = "project"
KEYWORD_FIELDS = ["user_id", "agent_id", "run_id", "actor_id", "type", "hash"]
DATETIME_FIELDS = ["created_at"]
# project -> models.KeywordIndexParams(type="keyword", is_tenant=True)
```

**Tratamento de erros:** o resolvedor degrada para a coleção configurada por env se `migration_state` estiver ausente (compatível com pré-migração). Falhas de dual-write/cópia são idempotentes por ID de ponto e registradas em `write_audit_logs`/log estruturado; jobs de migração retomam pelo `scroll_cursor`.

### Modelos de Dados

Nova tabela `migration_state` (singleton lógico — uma linha por migração ativa):

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | int (PK) | Identificador da migração |
| `source_collection` | text | Coleção blue (origem) |
| `target_collection` | text | Coleção green (destino) |
| `active_collection` | text | Coleção servida no momento (ponteiro do flip) |
| `dual_write_enabled` | bool | Liga a escrita dupla durante a janela |
| `scroll_cursor` | text (nullable) | Checkpoint da cópia (offset de `scroll`) |
| `status` | enum | `planned`, `copying`, `validating`, `flipped`, `rolled_back`, `done` |
| `updated_at` | datetime | Última atualização |

Extensão da tabela `projects` (já existente, com `name` PK e `memory_count`):

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `partition_tier` | enum (`shared`/`dedicated`) | Camada de particionamento do projeto |
| `shard_key` | text (nullable) | Shard key dedicado quando promovido |

**Payload Qdrant (inalterado em formato):** os pontos mantêm `project`, `type`, `created_at`, `hash`, `data`, etc.; muda apenas a **indexação** desses campos.

### Endpoints de API

Operacional (consumido pelo operador/painel), sob o prefixo administrativo existente:

| Método | Caminho | Descrição |
|--------|---------|-----------|
| GET | `/admin/projects/sizes` | Lista projetos com `memory_count`, `partition_tier`, `shard_key` e flag de proximidade do limiar |
| POST | `/admin/migration/start` | Provisiona green e inicia cópia (idempotente) |
| POST | `/admin/migration/flip` | Executa flip atômico após validação |
| POST | `/admin/migration/rollback` | Repontar `active_collection` para a blue |
| POST | `/admin/projects/{name}/promote` | Enfileira promoção do projeto a `shard_key` dedicado |

Contrato MCP (`search_memory`, `add_memories`) e `compat_v3` permanecem **sem alteração de assinatura**.

## Pontos de Integração

- **Cluster Qdrant (3 nós, RF=2, ~6 shards)** — substitui o Qdrant single-node. Autenticação por API key/rede privada (modelo da Fase 1). Criação da coleção green com `sharding_method=CUSTOM`. Retry/idempotência por ID de ponto na cópia e no dual-write.
- **PostgreSQL (Fase 0+1)** — fonte de verdade do estado de migração e do catálogo `projects`. Acesso via PgBouncer já existente.
- **fastembed/BM25** — slot `bm25` já criado por `create_col`; a coleção green nasce apta a busca híbrida (ativação fora desta fase).

## Análise de Impacto

| Componente | Tipo de Impacto | Descrição e Risco | Ação Necessária |
|------------|-----------------|-------------------|-----------------|
| `mem0/vector_stores/qdrant.py` | modificado | Índice de inquilino + índices `type`/`created_at`/`hash`; criação com shard/replicação; `shard_key_selector`. Risco médio (caminho crítico de busca). | Estender `_create_filter_indexes`/`create_col`/`search`; testes de regressão de filtro. |
| `utils/memory.py` | modificado | Resolução dinâmica da coleção ativa em vez de nome fixo. Risco médio. | Novo `PartitionResolver` + cache/invalidação. |
| `workers/write_worker.py` | modificado | Dual-write condicional; usar coleção ativa. Risco médio (frescor/duplicidade). | Injetar dual-write idempotente. |
| `workers/migration_worker.py` | novo | Cópia/validação/flip/promoção. Risco alto (volume). | Implementar com checkpoint e idempotência. |
| `models.py` + Alembic | novo/modificado | `migration_state` + colunas em `projects`. Risco baixo. | Migration nova. |
| `mcp_server.py`, `compat_v3.py` | modificado | Obter coleção via resolvedor; filtro inalterado. Risco baixo. | Trocar fonte do `collection_name`. |
| Deploy (Swarm) | novo/modificado | Cluster Qdrant + serviço migration-worker. Risco médio (infra). | Provisionar cluster e novo serviço. |

## Abordagem de Testes

### Testes Unitários

- `Qdrant._create_filter_indexes`: cria `project` como inquilino e os índices novos; não regride os existentes; no-op em local/single-node.
- `_create_filter`: filtro de projeto e cross-project (sem filtro / `in`) continuam corretos com o índice presente.
- `PartitionResolver`: resolve blue/green conforme `migration_state`; cache e invalidação no flip/promoção; fallback para env quando não há estado.
- Dual-write: idempotência por ID; grava em ambas só quando habilitado.
- Migração: retomada a partir do `scroll_cursor`; idempotência de `upsert` em reexecução.

### Testes de Integração

- **Blue-green ponta a ponta** (Qdrant de teste): popular blue → iniciar cópia → dual-write de novas escritas → validar paridade de contagem/amostra → flip → confirmar leitura na green; depois `rollback` e confirmar retorno à blue.
- **Isolamento e cross-project**: buscas escopadas por projeto e cross-project retornam o mesmo conjunto antes/depois da migração.
- **Promoção de gigante**: projeto acima do limiar recebe `shard_key`, pontos migram, busca escopada usa `shard_key_selector` e mantém resultados.
- **Carga/latência (validação do PRD)**: medir p99 de busca por projeto e cross-project sob carga representativa antes do flip, comparando blue vs green (latência plana).
- **Ambiente:** cluster Qdrant multi-nó de teste + PostgreSQL; dados sintéticos com distribuição de tamanhos por projeto (incluindo um gigante).

## Sequenciamento de Desenvolvimento

### Ordem de Construção

1. **Modelo de estado** (`migration_state` + colunas em `projects` + migration Alembic) — sem dependências.
2. **Extensão do provider Qdrant** (índice de inquilino + índices novos + criação com shard/replicação) — sem dependências de código (usa cluster de teste).
3. **`PartitionResolver`** (resolução da coleção ativa + cache/invalidação) — depende do passo 1.
4. **Integração da leitura/escrita ao resolvedor** (`mcp_server`, `compat_v3`, `write_worker` lendo coleção ativa) — depende dos passos 2 e 3.
5. **Dual-write no write-worker** (condicional por flag) — depende do passo 4.
6. **Worker de migração — cópia + checkpoint** (`scroll`→`upsert`, retomada) — depende dos passos 2 e 1.
7. **Validação + flip + rollback** (endpoints `/admin/migration/*`) — depende dos passos 5 e 6.
8. **Promoção de projeto gigante** (`shard_key` + reescrita + `shard_key_selector` na busca) — depende dos passos 2, 6 e 7.
9. **Visibilidade operacional** (`/admin/projects/sizes`, métricas/alertas de tamanho) — depende do passo 1.

### Dependências Técnicas

- **Cluster Qdrant provisionado** (3 nós, RF=2, ~6 shards) com versão que suporte `is_tenant` e custom sharding — bloqueia passos 2, 6–8.
- **Capacidade de hardware/armazenamento** suficiente para blue + green simultâneas durante a janela (pergunta em aberto do PRD).
- **PostgreSQL/PgBouncer** da Fase 0+1 disponíveis — bloqueia passos 1, 3.

## Monitoramento e Observabilidade

- **Métricas:** `qdrant_collection_size` por projeto; `qdrant_search_latency_p99` por escopo (projeto vs cross-project); `migration_copy_progress` (% / cursor); `dual_write_errors`; `project_size_over_threshold` (gauge/contagem). Reaproveitar `mcp_search_latency_p99` da Fase 1 como linha de base do "antes/depois".
- **Logs estruturados:** eventos de `migration` (start/copy-batch/validate/flip/rollback) com `migration_id` e cursor; eventos de `promotion` com `project`/`shard_key`; falhas de dual-write com `point_id`.
- **Alertas:** `qdrant_collection_size` de projeto > 20M (promover); `migration_copy` parado (sem avanço de cursor) por > N min; `dual_write_errors` > 0; p99 de busca pós-flip acima da meta da Fase 1 (gatilho de rollback).

## Considerações Técnicas

### Decisões-Chave

- **Decisão:** índice de inquilino (`is_tenant=true`) na coleção compartilhada + promoção por `shard_key` sob demanda. **Justificativa:** latência plana e cross-project barato sem multiplicar coleções. **Trade-offs:** isolamento lógico, não físico. **Alternativas rejeitadas:** coleção por projeto e sharding por projeto desde o início (ADR-001, ADR-002).
- **Decisão:** migração blue-green com worker dedicado e estado em PostgreSQL. **Justificativa:** zero downtime, retomável e reversível. **Trade-offs:** escrita/armazenamento duplicados temporários e indireção na resolução de coleção. **Alternativas rejeitadas:** in-place, estender write-worker, script one-shot (ADR-003).
- **Decisão:** cluster 3 nós, RF=2, ~6 shards. **Justificativa:** resiliência a 1 nó com custo equilibrado. **Trade-offs:** menos redundância que RF=3. **Alternativa rejeitada:** RF=3 e single-node.

### Riscos Conhecidos

- **Suporte do Qdrant a `is_tenant`/custom sharding** (média): validar versão antes; parametrizar criação de índice/coleção.
- **Divergência blue/green** (média): dual-write idempotente + validação de paridade antes do flip + reconciliação por cursor.
- **Pressão de armazenamento na janela dupla** (média): agendar com folga; descartar blue logo após estabilização.
- **Calibração do limiar de promoção** (média): limiar parametrizável + alertas; observar antes de fixar — área que pede medição em produção.
- **Custo do índice de inquilino em base grande** (baixa, mitigada): índice criado na green **antes** da carga, nunca na coleção viva.

## Registros de Decisão de Arquitetura

- [ADR-001: Particionamento lógico por projeto na coleção compartilhada (multitenancy por payload)](adrs/adr-001.md) — Particionar por projeto dentro de um repositório compartilhado, em vez de coleção física por projeto.
- [ADR-002: Índice de inquilino (is_tenant) com promoção por shard key dedicado e cluster 3 nós](adrs/adr-002.md) — Implementar o particionamento com `project` como índice de inquilino e custom sharding sob demanda, sobre cluster RF=2.
- [ADR-003: Migração blue-green com worker dedicado e estado no PostgreSQL](adrs/adr-003.md) — Repartir a base via blue-green (cópia com checkpoint + dual-write + flip), conduzida por worker dedicado e reversível.
