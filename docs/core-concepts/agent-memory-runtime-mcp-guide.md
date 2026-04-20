# Agent Memory Runtime MCP Guide

Практическая документация по `MCP`-интерфейсу `Agent Memory Runtime`.

Этот документ описывает уже реализованный `MCP` facade:

- transport
- JSON-RPC envelope
- поддерживаемые methods
- tools
- resources
- prompts
- примеры запросов
- типовые ошибки и ограничения

Связанные документы:

- [agent-memory-runtime-mcp-spec-v1.md](/Users/slava/Documents/mem0-src/docs/core-concepts/agent-memory-runtime-mcp-spec-v1.md)
- [agent-memory-runtime-system-design-v1.md](/Users/slava/Documents/mem0-src/docs/core-concepts/agent-memory-runtime-system-design-v1.md)
- [memory-runtime/README.md](/Users/slava/Documents/mem0-src/memory-runtime/README.md)

## 1. Что это такое

`MCP` в нашем проекте это thin compatibility layer поверх уже существующих runtime services.

Он:

- не заменяет `REST API`
- не вводит отдельную business logic ветку
- использует те же retrieval/observability/repository слои
- нужен для MCP-aware клиентов, которым удобнее работать через standard tools/resources/prompts

## 2. Endpoint

Текущий transport:

- `POST /mcp/{client_name}/http/{user_id}`

Пример полного URL:

- `http://localhost:8080/mcp/openclaw/http/alice`

Где:

- `client_name` — имя интеграции или клиента
- `user_id` — внешний user/session identifier клиента

Транспорт stateless:

- сервер не хранит MCP session state
- `DELETE` на этот endpoint возвращает `405`

## 3. Обязательные заголовки

Для каждого MCP-запроса нужны:

- `Accept: application/json`
- `Content-Type: application/json`

Если `Accept` не содержит `application/json`, сервер вернет `406`.
Если `Content-Type` указан и не является `application/json`, сервер вернет `415`.

## 4. JSON-RPC envelope

Поддерживается `JSON-RPC 2.0`.

Минимальная форма запроса:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {}
}
```

Общий формат ответа:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {}
}
```

Общий формат ошибки:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32601,
    "message": "Method '...' is not supported by this MCP server."
  }
}
```

## 5. Поддерживаемые methods

Сейчас реализованы:

- `initialize`
- `tools/list`
- `tools/call`
- `resources/templates/list`
- `resources/read`
- `prompts/list`
- `prompts/get`

## 6. Initialize

Пример:

```bash
curl -s http://localhost:8080/mcp/openclaw/http/alice \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {
        "name": "openclaw",
        "version": "0.1.0"
      }
    }
  }'
```

Ответ содержит:

- `protocolVersion`
- `serverInfo`
- `capabilities`

## 7. Tools

### 7.1 `tools/list`

Возвращает весь текущий реестр MCP tools.

Пример:

```bash
curl -s http://localhost:8080/mcp/openclaw/http/alice \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

### 7.2 Доступные tools

#### `memory.recall`

Назначение:

- собрать `MemoryBrief` для текущего запроса

Аргументы:

- `namespace_id`
- `agent_id`
- `session_id`
- `query`
- `context_budget_tokens`
- optional `space_filter`

Пример:

```bash
curl -s http://localhost:8080/mcp/openclaw/http/alice \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "memory.recall",
      "arguments": {
        "namespace_id": "NAMESPACE_ID",
        "agent_id": "AGENT_ID",
        "query": "What architecture context already exists for the memory runtime?",
        "context_budget_tokens": 900
      }
    }
  }'
```

`structuredContent` содержит:

- `brief`
- `trace`

Дополнительно runtime пишет `recall_executed` в `audit_log`, чтобы последний recall был доступен как MCP resource.

#### `memory.search`

Назначение:

- поиск по активной long-term памяти

Аргументы:

- `namespace_id`
- optional `agent_id`
- `query`
- optional `limit`
- optional `space_types`

Пример:

```bash
curl -s http://localhost:8080/mcp/openclaw/http/alice \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "memory.search",
      "arguments": {
        "namespace_id": "NAMESPACE_ID",
        "agent_id": "AGENT_ID",
        "query": "What storage stack does the runtime use?",
        "limit": 5
      }
    }
  }'
```

Каждый result содержит:

- `id`
- `summary`
- `content`
- `kind`
- `scope`
- `space_type`
- `score`
- `status`
- `updated_at`

#### `memory.list_spaces`

Назначение:

- перечислить видимые memory spaces

Аргументы:

- `namespace_id`
- optional `agent_id`

Пример:

```bash
curl -s http://localhost:8080/mcp/openclaw/http/alice \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/call",
    "params": {
      "name": "memory.list_spaces",
      "arguments": {
        "namespace_id": "NAMESPACE_ID",
        "agent_id": "AGENT_ID"
      }
    }
  }'
```

#### `memory.get_observability_snapshot`

Назначение:

- получить текущий operational snapshot runtime

Аргументы:

- не обязательны

Пример:

```bash
curl -s http://localhost:8080/mcp/openclaw/http/alice \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 6,
    "method": "tools/call",
    "params": {
      "name": "memory.get_observability_snapshot",
      "arguments": {}
    }
  }'
```

Ответ содержит:

- `metrics`
- `jobs`

#### `memory.get_memory_unit`

Назначение:

- получить один конкретный `memory_unit`

Аргументы:

- `namespace_id`
- `memory_unit_id`
- optional `agent_id`

Пример:

```bash
curl -s http://localhost:8080/mcp/openclaw/http/alice \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 7,
    "method": "tools/call",
    "params": {
      "name": "memory.get_memory_unit",
      "arguments": {
        "namespace_id": "NAMESPACE_ID",
        "agent_id": "AGENT_ID",
        "memory_unit_id": "MEMORY_UNIT_ID"
      }
    }
  }'
```

## 8. Resource templates

### 8.1 `resources/templates/list`

Возвращает поддерживаемые URI templates.

Сейчас доступны:

- `memory://namespaces/{namespace_id}/summary`
- `memory://namespaces/{namespace_id}/agents/{agent_id}/brief`
- `memory://namespaces/{namespace_id}/observability`
- `memory://namespaces/{namespace_id}/agents/{agent_id}/spaces`

### 8.2 `resources/read`

Пример:

```bash
curl -s http://localhost:8080/mcp/openclaw/http/alice \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 8,
    "method": "resources/read",
    "params": {
      "uri": "memory://namespaces/NAMESPACE_ID/summary"
    }
  }'
```

Ответ всегда содержит `contents`, внутри которых лежит:

- `uri`
- `mimeType`
- `text`

### 8.3 Resource meanings

#### `memory://namespaces/{namespace_id}/summary`

Возвращает:

- namespace metadata
- agents
- `space_counts`
- `active_memory_unit_count`

#### `memory://namespaces/{namespace_id}/agents/{agent_id}/brief`

Возвращает:

- `last_recall`
- `recorded_at`

Если recall еще не вызывался, `last_recall` будет `null`.

#### `memory://namespaces/{namespace_id}/observability`

Возвращает:

- observability snapshot
- namespace metadata

#### `memory://namespaces/{namespace_id}/agents/{agent_id}/spaces`

Возвращает:

- видимые пространства памяти для агента

## 9. Prompts

### 9.1 `prompts/list`

Возвращает реестр доступных prompts.

Сейчас доступны:

- `debug-memory-miss`
- `prepare-memory-aware-task`
- `inspect-namespace-health`

### 9.2 `prompts/get`

Пример:

```bash
curl -s http://localhost:8080/mcp/openclaw/http/alice \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 9,
    "method": "prompts/get",
    "params": {
      "name": "prepare-memory-aware-task",
      "arguments": {
        "namespace_id": "NAMESPACE_ID",
        "agent_id": "AGENT_ID",
        "task": "prepare the next OpenClaw integration milestone"
      }
    }
  }'
```

Ответ содержит:

- `description`
- `messages`

### 9.3 Prompt meanings

#### `debug-memory-miss`

Нужен для разбора ситуации, когда память не вернула ожидаемое воспоминание.

Аргументы:

- `namespace_id`
- `agent_id`
- `expected_memory`
- optional `query`

#### `prepare-memory-aware-task`

Нужен как scaffold для workflow, где агент сначала делает `memory.recall`, а потом продолжает задачу.

Аргументы:

- `namespace_id`
- optional `agent_id`
- optional `session_id`
- `task`

#### `inspect-namespace-health`

Нужен для operator/debugging сценариев вокруг health и backlog памяти.

Аргументы:

- `namespace_id`

## 10. Ограничения текущей реализации

Сейчас MCP layer:

- stateless
- read-first
- не поддерживает safe write tools
- не поддерживает realtime subscriptions
- не реализует отдельную auth model поверх runtime

Пока не поддерживается:

- `memory.ingest_event`
- `memory.record_feedback`
- destructive admin operations

## 11. Следующие шаги

Следующие согласованные задачи по MCP:

- добавить safe write MCP tools:
  - `memory.ingest_event`
  - `memory.record_feedback`
- ввести для них guardrails:
  - обязательный namespace scope
  - обязательный agent scope там, где write agent-scoped
  - запрет на direct durable-memory bypass
  - запрет на lifecycle/admin mutation через MCP
- подготовить маленький MCP client smoke script для быстрого подключения и проверки реального `OpenClaw`

Практический смысл smoke script:

- быстро проверить `initialize`
- быстро проверить `tools/list`
- быстро проверить `memory.recall`
- быстро проверить transport/headers без полного live-сценария

## 12. Типовые ошибки

### `406`

Причина:

- нет `Accept: application/json`

### `415`

Причина:

- неправильный `Content-Type`

### `400`

Причина:

- невалидный JSON body
- JSON-RPC payload не является object

### JSON-RPC `-32601`

Причина:

- неизвестный `method`

### JSON-RPC `-32602`

Причина:

- отсутствует обязательный аргумент
- невалидный URI resource
- невалидный tool arguments payload

### JSON-RPC `-32004`

Причина:

- не найден namespace
- не найден agent
- не найден memory unit

## 13. Наблюдаемость

Через `/metrics` экспортируются:

- `memory_runtime_mcp_requests_total`
- `memory_runtime_mcp_tool_calls_total`
- `memory_runtime_mcp_resource_reads_total`
- `memory_runtime_mcp_prompt_requests_total`
- `memory_runtime_mcp_errors_total`

Это полезно для:

- проверки, что MCP-клиент реально ходит в runtime
- оценки интенсивности tool/resource/prompt usage
- диагностики protocol-level ошибок

## 14. Рекомендуемый flow интеграции

Практически для нового MCP-aware клиента я бы рекомендовал такой порядок:

1. `initialize`
2. `tools/list`
3. `resources/templates/list`
4. `prompts/list`
5. использовать `memory.recall` как основной operational tool
6. использовать `memory.search` и `memory.get_memory_unit` для debugging и inspection
7. использовать resources для read-only context и operator workflows

## 15. Текущий статус

Текущая реализация уже покрыта component tests:

- MCP transport validation
- tool calls
- resource reads
- prompt responses
- metrics export

Текущий рабочий baseline:

- пригоден для MCP-aware read-first интеграций
- не заменяет REST adapters
- хорошо подходит как compatibility layer и inspection surface
