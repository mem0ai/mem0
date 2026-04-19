# Memory Runtime

`memory-runtime` — отдельный сервисный контур для `Agent Memory Runtime`, который строится поверх `mem0-core`.

На текущем этапе это scaffold первой версии сервиса:

- FastAPI приложение
- конфигурация через environment variables
- health endpoint
- namespace, event, recall, and adapter APIs
- Dockerfile
- Docker Compose для локального старта
- минимальная test harness
- `Makefile` с базовыми dev и quality командами

## Структура

```text
memory-runtime/
  app/
  tests/
  .env.example
  Makefile
  Dockerfile
  docker-compose.yml
  pyproject.toml
```

## Конфигурация

Скопируй шаблон переменных окружения:

```bash
cd memory-runtime
cp .env.example .env
```

Основные переменные:

- `MEMORY_RUNTIME_APP_NAME`
- `MEMORY_RUNTIME_ENV`
- `MEMORY_RUNTIME_DEBUG`
- `MEMORY_RUNTIME_API_PORT`
- `MEMORY_RUNTIME_WORKER_POLL_SECONDS`
- `MEMORY_RUNTIME_POSTGRES_DSN`
- `MEMORY_RUNTIME_REDIS_URL`
- `MEMORY_RUNTIME_MEM0_BRIDGE_ENABLED`
- `MEMORY_RUNTIME_MEM0_BASE_URL`
- `MEMORY_RUNTIME_MEM0_API_KEY`

По умолчанию локальный scaffold использует SQLite-файл для безопасного старта без внешней БД.
Для Docker и реального runtime используется явный Postgres DSN из `.env`.
`mem0 bridge` по умолчанию выключен и включается только явной конфигурацией.

## Установка dev-зависимостей

```bash
cd memory-runtime
python3 -m pip install -e '.[dev]'
```

## Локальный запуск

```bash
cd memory-runtime
make run
make run-worker
```

## Docker Compose

```bash
cd memory-runtime
cp .env.example .env
docker compose up --build
```

Сервис будет доступен на:

- `http://localhost:8080`
- `http://localhost:8080/healthz`
- `http://localhost:8080/docs`

Compose baseline теперь поднимает:

- `memory-api`
- `memory-worker`
- `postgres`
- `redis`

Readiness baseline теперь включает:

- healthcheck для `postgres`
- healthcheck для `redis`
- heartbeat-based healthcheck для `memory-worker`
- `service_healthy` dependencies для API и worker

Для первого живого MVP-пилота с `OpenClaw` смотри runbook:
- [agent-memory-runtime-openclaw-pilot-runbook.md](/Users/slava/Documents/mem0-src/docs/core-concepts/agent-memory-runtime-openclaw-pilot-runbook.md)

## API surface

Уже реализованы:

- `GET /metrics`
- `POST /v1/namespaces`
- `GET /v1/namespaces/{namespace_id}`
- `POST /v1/namespaces/{namespace_id}/agents`
- `POST /v1/events`
- `POST /v1/recall`
- `POST /v1/recall/feedback`
- `GET /v1/observability/stats`
- `POST /v1/adapters/openclaw/bootstrap`
- `POST /v1/adapters/openclaw/events`
- `POST /v1/adapters/openclaw/recall`
- `POST /v1/adapters/openclaw/search`
- `GET /v1/adapters/openclaw/memories`
- `GET /v1/adapters/openclaw/memories/{memory_id}`
- `DELETE /v1/adapters/openclaw/memories/{memory_id}`
- `POST /v1/adapters/bunkerai/events`
- `POST /v1/adapters/bunkerai/recall`

Адаптерные endpoints фиксируют source-system contract для интеграций и работают поверх того же ingestion/recall pipeline.
Для `OpenClaw` добавлен отдельный runtime-contract: плагин сначала вызывает `bootstrap`, затем использует `events/search/list/get/delete` как transport-поверхность вместо прямого подключения к `mem0`.
Long-term `search/list` в adapter contract теперь возвращают только long-term candidates и не подтягивают `session-space`; уже консолидированные эпизоды не дублируются рядом с `memory_units`.
В shared namespace `shared-space` доступен межагентно, при этом `agent-core` остается приватным.
`/metrics` отдает Prometheus-compatible экспорт counters и job gauges, а `/v1/observability/stats` дает JSON-срез для локальной диагностики и dashboard bootstrap.
Worker-derived operational counters (`jobs_*`, `consolidation_*`, `lifecycle_*`) теперь считаются из shared DB state (`jobs` и `audit_log`), а не только из process-local памяти.
`/v1/observability/stats` также показывает `oldest_pending_age_seconds` и `stalled_running_count`, чтобы было проще увидеть backlog или зависшие worker jobs.
`/v1/recall/feedback` записывает usefulness signals, которые потом участвуют в последующем ranking.
При включенном `mem0 bridge` runtime может синхронизировать long-term memories в `mem0` и использовать его как внешний recall source.

## Тесты

Базовые scaffold-тесты покрывают:

- конфигурацию по умолчанию и через environment variables
- health endpoint
- namespace and agent API baseline
- event ingestion and episode creation baseline
- recall baseline and `MemoryBrief` structure
- consolidation jobs, worker processing, and `memory_units` baseline
- lifecycle jobs, decay/archive/eviction baseline, and internal metrics counters
- adapter contracts for `OpenClaw` and `BunkerAI`
- OpenClaw runtime adapter coverage for bootstrap, search, list, get, and delete
- shared namespace e2e scenario for cross-agent memory exchange
- OpenClaw pilot e2e continuity flow
- Prometheus-style metrics exporter and observability stats endpoint
- recall feedback loop and usefulness-aware reranking
- mem0 bridge unit coverage without external network dependency

Команды запуска:

```bash
cd memory-runtime
make test-unittest
make test
make test-e2e
make pilot-smoke
```

`make pilot-smoke` поднимает Docker stack, прогоняет synthetic OpenClaw pilot contour и сохраняет JSON report в `.artifacts/openclaw_pilot_smoke_report.json`.

Миграции:

```bash
cd memory-runtime
make migrate
```

## Quality workflow

Локальные проверки:

```bash
cd memory-runtime
make lint
make test
```

Fallback smoke suite без `pytest`:

```bash
cd memory-runtime
make smoke
```

Текущие scaffold-тесты совместимы и с `unittest`, и с `pytest`.
