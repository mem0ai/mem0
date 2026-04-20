# Agent Memory Runtime MCP Spec v1

Спецификация `MCP`-интерфейса для `Agent Memory Runtime`.

На текущий момент read-first `MCP` facade уже реализован в baseline-объеме:

- stateless `POST /mcp/{client_name}/http/{user_id}`
- `initialize`
- `tools/list`, `tools/call`
- `resources/templates/list`, `resources/read`
- `prompts/list`, `prompts/get`
- базовые `MCP` counters в `/metrics`

Документ фиксирует и текущую реализацию, и целевой compatibility layer поверх уже существующего runtime API.

Связанные артефакты:

- [agent-memory-runtime-v1.md](/Users/slava/Documents/mem0-src/docs/core-concepts/agent-memory-runtime-v1.md)
- [agent-memory-runtime-system-design-v1.md](/Users/slava/Documents/mem0-src/docs/core-concepts/agent-memory-runtime-system-design-v1.md)
- [agent-memory-runtime-implementation-plan-v1.md](/Users/slava/Documents/mem0-src/docs/core-concepts/agent-memory-runtime-implementation-plan-v1.md)

## 1. Зачем нам MCP

`MCP` нужен не для улучшения качества памяти как такового, а для улучшения интеграции.

Цели:

- дать агентным клиентам стандартный интерфейс доступа к памяти
- упростить подключение новых клиентов без отдельного bespoke SDK
- сделать memory-runtime discoverable как tool/resource provider
- сохранить `REST API` как primary internal contract и добавить `MCP` как thin facade

Не-цели:

- не заменять текущий `REST` слой
- не переносить всю бизнес-логику в `MCP`
- не делать `MCP` основным write-path в первой версии

## 2. Продуктовая гипотеза

`MCP` для memory-runtime даст наибольшую пользу в трех сценариях:

1. агентные клиенты и IDE-среды, которые уже понимают `MCP`
2. быстрый onboarding новых интеграций без отдельного runtime SDK
3. более прозрачный inspection/debugging памяти через standard resources/tools

Главная идея:

`memory-runtime` остается memory engine + orchestration service, а `MCP` становится standardized access layer.

## 3. Принципы дизайна

- `REST-first, MCP-second`
- `read-heavy first`
- `thin translation layer`
- `no duplicated semantics`
- `safe-by-default`
- `tooling for recall/debugging first, memory mutation later`

Следствие:

- все `MCP` calls должны маппиться на уже существующие application services
- нельзя заводить отдельную MCP-only бизнес-логику recall/consolidation/lifecycle

## 4. Scope v1

### Входит в v1

- read-only memory tools
- read-only resources для inspection/debugging
- ограниченный набор prompts для debugging и memory-aware workflows
- namespace/agent scoped access
- recall trace visibility

### Не входит в v1

- произвольные destructive admin operations
- lifecycle mutation через MCP
- прямой write в durable memory без использования существующих ingestion rules
- сложная подписка на realtime stream updates

## 5. Capability Model

Текущий MCP server уже поддерживает три capability-группы:

- `tools`
- `resources`
- `prompts`

Текущая последовательность rollout:

1. `tools + resources` — реализовано
2. `prompts` — реализовано в baseline-объеме
3. optional safe write tools — отложено

## 6. Tools v1

### 6.1 `memory.recall`

Назначение:

- получить `MemoryBrief` под текущую задачу

Вход:

- `namespace_id`
- `agent_id`
- `session_id`
- `query`
- `context_budget_tokens`
- optional `space_filter`

Выход:

- `brief`
- `trace`

REST mapping:

- `POST /v1/recall`

### 6.2 `memory.search`

Назначение:

- выполнить search по long-term/session memory через adapter-like semantics

Вход:

- `namespace_id`
- `agent_id`
- optional `session_id`
- `query`
- `limit`

Выход:

- ranked memory results

Runtime mapping:

- MCP facade использует существующие repositories/runtime services без отдельного public REST endpoint

### 6.3 `memory.list_spaces`

Назначение:

- показать доступные memory spaces для namespace/agent

Вход:

- `namespace_id`
- optional `agent_id`

Выход:

- список пространств памяти
- тип пространства
- режим `shared/isolated`

REST mapping:

- новый runtime endpoint или aggregation поверх существующих repositories

### 6.4 `memory.get_observability_snapshot`

Назначение:

- быстро получить operational state runtime

Вход:

- optional `namespace_id`

Выход:

- `jobs.by_status`
- counters
- stalled/pending hints

REST mapping:

- `GET /v1/observability/stats`

### 6.5 `memory.get_memory_unit`

Назначение:

- inspection конкретного durable memory object

Вход:

- `memory_id`
- `namespace_id`

Выход:

- summary / content
- scope / kind / status
- timestamps

REST mapping:

- новый runtime endpoint

## 7. Resources v1

Resources нужны для read-only контекста, который клиент сам решает когда читать.

### 7.1 `memory://namespaces/{namespace_id}/summary`

Содержимое:

- namespace mode
- source systems
- agents count
- spaces count
- краткая operational summary

### 7.2 `memory://namespaces/{namespace_id}/agents/{agent_id}/brief`

Содержимое:

- last recall brief
- selected spaces
- selected episode ids

### 7.3 `memory://namespaces/{namespace_id}/observability`

Содержимое:

- counters
- job snapshot
- stalled running count

### 7.4 `memory://namespaces/{namespace_id}/agents/{agent_id}/spaces`

Содержимое:

- agent-core
- project-space
- session-space
- shared-space if enabled

## 8. Prompts v1

Prompts не должны быть “магией”, а удобными operator/debugging шаблонами.

### 8.1 `debug-memory-miss`

Назначение:

- помочь разобрать, почему нужная память не попала в recall

Ожидаемый контекст:

- recall query
- trace
- selected items
- observability snapshot

### 8.2 `prepare-memory-aware-task`

Назначение:

- подготовить memory-aware prompt scaffold для внешнего агента

### 8.3 `inspect-namespace-health`

Назначение:

- быстро собрать operator-oriented diagnostic view

## 9. Write Path Policy

В первой MCP-версии write-path должен быть ограниченным.

### Разрешено позже

- `memory.ingest_event`
- `memory.record_feedback`

### Пока не разрешать

- `memory.force_create_long_term`
- `memory.delete_memory_unit`
- `memory.override_lifecycle`
- `memory.raw_admin_update`

Причина:

- durable memory write-path у нас чувствителен к poisoning, duplicates и policy bypass
- write operations должны проходить через уже существующие ingestion/consolidation rules

## 10. Auth and Scope Model

В первой self-hosted версии допускается простой scope model:

- server-side binding к namespace/agent
- optional token-based auth later
- explicit namespace ownership in every call

Инварианты:

- `agent-core` не должен утекать между агентами
- `shared-space` должен читаться только там, где namespace mode это разрешает
- `MCP` не должен ломать уже существующие namespace boundaries

## 11. Mapping to Existing Runtime

MCP server должен быть thin adapter над уже существующим runtime:

- `memory.recall` -> `RetrievalService`
- `memory.search` -> adapter/runtime search service
- `memory.get_observability_snapshot` -> `ObservabilityService`
- `memory.record_feedback` -> `Recall feedback service`

Нельзя:

- дублировать ranking logic внутри MCP server
- заводить MCP-only memory selection rules
- заводить второй источник истины по memory objects

## 12. Observability Requirements

Сам MCP layer тоже должен быть наблюдаем.

Нужно экспортировать:

- `mcp_requests_total`
- `mcp_tool_calls_total`
- `mcp_resource_reads_total`
- `mcp_prompt_requests_total`
- `mcp_errors_total`
- latency by capability type

Также полезно логировать:

- tool name
- namespace_id
- agent_id
- result size
- error class

## 13. Testing Strategy

### Unit

- schema translation
- REST-to-MCP mapping
- capability registration

### Component

- each tool contract
- each resource payload
- prompt registry

### Integration

- namespace isolation through MCP
- shared-space visibility through MCP

### E2E

- external MCP client can recall memory
- external MCP client can inspect observability snapshot

## 14. Risks

### 14.1 Surface area growth

Риск:

- второй integration surface увеличит поддержку

Снижение:

- thin facade only
- no duplicate logic

### 14.2 Policy bypass

Риск:

- если рано открыть write tools, можно обойти ingestion/consolidation guards

Снижение:

- read-only first
- safe write later

### 14.3 Contract drift

Риск:

- MCP response shape начнет расходиться с runtime semantics

Снижение:

- MCP built directly over existing services

## 15. Recommended Rollout

### Phase 1

- read-only MCP server
- tools: `memory.recall`, `memory.search`, `memory.get_observability_snapshot`
- resources: namespace summary, observability snapshot

Статус:

- `completed`

### Phase 2

- add prompts
- add `memory.list_spaces`
- add `memory.get_memory_unit`

Статус:

- `completed` в baseline-объеме

### Phase 3

- add safe write tools:
  - `memory.ingest_event`
  - `memory.record_feedback`

## 16. Final Recommendation

`MCP` стоит добавлять как post-pilot compatibility layer.

Правильная позиция для проекта:

- не заменять `REST`
- не строить новую memory semantics внутри MCP
- начать с `read-only MCP`
- использовать его как multiplier для integration convenience и adoption
