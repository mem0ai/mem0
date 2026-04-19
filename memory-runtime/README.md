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
- `MEMORY_RUNTIME_POSTGRES_DSN`
- `MEMORY_RUNTIME_REDIS_URL`

По умолчанию локальный scaffold использует SQLite-файл для безопасного старта без внешней БД.
Для Docker и реального runtime используется явный Postgres DSN из `.env`.

## Установка dev-зависимостей

```bash
cd memory-runtime
python3 -m pip install -e '.[dev]'
```

## Локальный запуск

```bash
cd memory-runtime
make run
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

## API surface

Уже реализованы:

- `GET /metrics`
- `POST /v1/namespaces`
- `GET /v1/namespaces/{namespace_id}`
- `POST /v1/namespaces/{namespace_id}/agents`
- `POST /v1/events`
- `POST /v1/recall`
- `GET /v1/observability/stats`
- `POST /v1/adapters/openclaw/events`
- `POST /v1/adapters/openclaw/recall`
- `POST /v1/adapters/bunkerai/events`
- `POST /v1/adapters/bunkerai/recall`

Адаптерные endpoints фиксируют source-system contract для интеграций и работают поверх того же ingestion/recall pipeline.
В shared namespace `shared-space` доступен межагентно, при этом `agent-core` остается приватным.
`/metrics` отдает Prometheus-compatible экспорт counters и job gauges, а `/v1/observability/stats` дает JSON-срез для локальной диагностики и dashboard bootstrap.

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
- shared namespace e2e scenario for cross-agent memory exchange
- Prometheus-style metrics exporter and observability stats endpoint

Команды запуска:

```bash
cd memory-runtime
make test-unittest
make test
```

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
