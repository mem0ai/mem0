# Agent Memory Runtime Implementation Plan v1

План реализации первой версии `Agent Memory Runtime` как отдельного сервиса поверх `mem0-core`.

Документ опирается на:

- [agent-memory-runtime-v1.md](/Users/slava/Documents/mem0-src/docs/core-concepts/agent-memory-runtime-v1.md)
- [agent-memory-runtime-system-design-v1.md](/Users/slava/Documents/mem0-src/docs/core-concepts/agent-memory-runtime-system-design-v1.md)

## Статус

- Draft v1
- Назначение: перевести system design в конкретный execution plan
- Фокус: структура репозитория, этапы реализации, testing strategy, release quality gates

## Текущий прогресс

На момент последнего обновления уже создан начальный scaffold сервиса в [memory-runtime/README.md](/Users/slava/Documents/mem0-src/memory-runtime/README.md):

- отдельный каталог `memory-runtime`
- FastAPI scaffold
- `healthz` endpoint
- конфигурация через environment variables
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `Makefile` для локальной разработки и quality checks
- базовые unit/component tests

### Статус `Phase A`

`Phase A` считается завершенной.

Подтвержденные результаты:

- сервисный каталог создан
- локальный FastAPI scaffold собран
- базовый dev flow задокументирован
- smoke/test harness присутствует
- базовые тесты проходят
- документация синхронизирована с кодом

## 1. Цели этапа

На этом этапе нужно подготовить основу для реализации нового сервиса так, чтобы:

- архитектура оставалась расширяемой
- запуск через Docker был простым
- код был изначально пригоден для тестирования
- качество релизов обеспечивалось не вручную, а через системные проверки

## 2. Принятые инженерные решения для старта

### Язык и runtime

Для `memory-runtime` v1 используется Python и FastAPI.

Причины:

- текущий `mem0-core` уже находится в Python
- существующий `server/main.py` дает reference surface для API
- в репозитории уже есть `pytest`-ориентированная база и FastAPI-контуры

### Базовый storage stack

- `Postgres + pgvector`
- `Redis`
- `Neo4j` опционально, не в первом обязательном контуре

### Основной стиль интеграции

`memory-runtime` не внедряется внутрь `mem0`, а создается как отдельный верхнеуровневый сервис, использующий `mem0` как библиотечное ядро.

## 3. Предлагаемая структура каталогов

Новый сервис лучше выделить в отдельный каталог верхнего уровня:

```text
memory-runtime/
  README.md
  Dockerfile
  docker-compose.yml
  pyproject.toml
  alembic.ini
  app/
    main.py
    config.py
    dependencies.py
    database.py
    models/
      __init__.py
      namespace.py
      agent.py
      memory_space.py
      memory_event.py
      episode.py
      memory_unit.py
      memory_link.py
      recall.py
      job.py
      audit.py
    schemas/
      __init__.py
      namespace.py
      event.py
      recall.py
      memory.py
    routers/
      __init__.py
      health.py
      namespaces.py
      events.py
      recall.py
      memories.py
      spaces.py
    services/
      __init__.py
      ingestion.py
      working_memory.py
      consolidation.py
      retrieval.py
      lifecycle.py
      briefing.py
      namespaces.py
    repositories/
      __init__.py
      namespaces.py
      events.py
      episodes.py
      memory_units.py
      recall.py
      jobs.py
    workers/
      __init__.py
      runner.py
      handlers/
        episode_compaction.py
        memory_consolidation.py
        memory_decay.py
        memory_eviction.py
    integrations/
      __init__.py
      mem0_core.py
      redis_queue.py
      optional_graph.py
    telemetry/
      __init__.py
      logging.py
      metrics.py
      traces.py
    utils/
      ids.py
      time.py
      tokens.py
      hashing.py
  migrations/
  tests/
    unit/
    component/
    integration/
    contract/
    e2e/
    fixtures/
      factories.py
      payloads.py
      golden/
```

## 4. Границы ответственности по слоям

### `routers`

Только HTTP layer:

- request parsing
- validation
- response formatting
- dependency injection

### `services`

Основная бизнес-логика:

- ingestion orchestration
- recall orchestration
- memory brief assembly
- consolidation decisions

### `repositories`

Изолируют SQLAlchemy / storage access.

### `integrations`

Тонкие адаптеры к внешним технологиям:

- `mem0-core`
- Redis queue
- optional graph backend

### `workers`

Фоновая обработка job'ов и lifecycle-задач.

## 5. Delivery roadmap

### Phase A. Bootstrap

Результат:

- каталог `memory-runtime`
- рабочий FastAPI app
- конфиг
- health endpoint
- Dockerfile
- compose-файл с Postgres и Redis

Definition of Done:

- сервис поднимается локально
- проходит smoke test
- документация обновлена
- есть базовые unit/component tests

Статус:

- `completed`

### Phase B. Core data model

Результат:

- таблицы `namespaces`, `agents`, `memory_spaces`, `memory_events`
- миграции
- repository layer
- namespace management endpoints

Definition of Done:

- миграции применяются чисто
- есть migration tests
- есть repository tests на базовые CRUD-операции

### Phase C. Event ingestion and working memory

Результат:

- `POST /v1/events`
- нормализация input
- запись memory events
- episode formation v1
- session-space persistence

Definition of Done:

- есть component tests для API
- есть unit tests на normalization/segmentation
- есть integration tests с Postgres

### Phase D. Retrieval MVP

Результат:

- `POST /v1/recall`
- scope resolution
- candidate gathering
- simple rerank
- brief builder v1

Definition of Done:

- есть golden tests на format и content structure `MemoryBrief`
- есть contract tests на recall payloads
- есть regression tests на ranking logic

### Phase E. Consolidation pipeline

Результат:

- queue
- worker
- consolidation jobs
- create/update/merge semantics
- promotion into spaces

Definition of Done:

- есть integration tests API + queue + DB + worker
- есть scenario tests short-term -> long-term
- есть audit trail tests

### Phase F. Lifecycle management

Результат:

- TTL for session-space
- decay
- eviction
- compression hooks

Definition of Done:

- есть deterministic lifecycle tests
- есть time-based tests с controllable clock
- есть regression tests на non-lossy compression expectations

### Phase G. Adapters

Результат:

- OpenClaw adapter contract
- BunkerAI adapter contract
- shared namespace mode

Definition of Done:

- есть contract tests на оба адаптера
- есть e2e shared namespace scenario

## 6. Первые технические backlog items

### Iteration 1

- создать `memory-runtime/`
- добавить `README.md` сервиса
- создать `pyproject.toml`
- собрать FastAPI приложение
- добавить `/healthz`
- добавить конфиг через environment variables
- добавить базовый Docker Compose

### Iteration 2

- подключить Postgres
- подключить Redis
- описать SQLAlchemy models
- поднять Alembic
- реализовать `POST /v1/namespaces`
- реализовать `POST /v1/namespaces/{id}/agents`

### Iteration 3

- реализовать `POST /v1/events`
- сделать event normalization
- добавить запись `memory_events`
- сделать episode builder v1

### Iteration 4

- реализовать `POST /v1/recall`
- реализовать retrieval service v1
- реализовать brief formatter v1

### Iteration 5

- добавить queue worker
- реализовать `memory_consolidation`
- интегрировать `mem0-core`

## 7. Тестовая стратегия

Это обязательная часть проекта, а не второстепенная активность.

Цель тестовой системы:

- предотвращать регрессии recall quality
- предотвращать silent corruption memory lifecycle
- удерживать предсказуемое поведение на релизах
- делать архитектурные изменения безопасными

## 8. Тестовая пирамида

### 8.1 Unit tests

Проверяют чистую логику без реальной БД и сетевых зависимостей.

Что покрываем:

- normalization rules
- space resolution
- scoring functions
- memory brief packing
- lifecycle decisions
- conflict resolution helpers
- idempotency logic

Цель:

- очень быстрые
- запускаются на каждом изменении

### 8.2 Component tests

Проверяют один модуль сервиса с подмененными внешними интеграциями.

Что покрываем:

- API routers
- service layer
- repository contracts с test DB
- worker handlers с fake queue/mem0 adapters

### 8.3 Integration tests

Проверяют связку реальных компонентов:

- FastAPI + Postgres
- FastAPI + Redis
- API + worker + database
- migrations + repositories

Что особенно важно:

- корректность схемы данных
- job processing
- сохранение и чтение memory events / units / briefs

### 8.4 Contract tests

Проверяют совместимость integration surfaces.

Что покрываем:

- payload contracts для `OpenClaw`
- payload contracts для `BunkerAI`
- backward-compatible shape ответов `/v1/recall`
- explicit memory operations

### 8.5 End-to-end tests

Проверяют полные продуктовые сценарии на Docker stack.

Минимальный набор сценариев:

1. агент пишет события -> появляется session memory
2. consolidation переносит полезное знание в long-term
3. recall возвращает brief с нужными слотами
4. shared namespace работает для двух агентов
5. isolated namespaces не протекают друг в друга

### 8.6 Regression and golden tests

Критично для качества recall.

Покрываем:

- `MemoryBrief` output
- consolidation decisions
- ranking outcomes
- promotion into spaces

Формат:

- фиксированные входы
- фиксированные ожидаемые outputs
- осознанное обновление golden files только при принятом изменении поведения

## 9. Рекомендуемый test stack

Для Python-сервиса:

- `pytest`
- `pytest-asyncio`
- `httpx` для API tests
- `pytest-cov`
- `pytest-mock`

Дополнительно рекомендую:

- `freezegun` или эквивалент для time-based lifecycle tests
- `testcontainers` или docker-compose based integration harness
- `factory-boy` или легковесные factories в `tests/fixtures/factories.py`

Для TypeScript adapters:

- `vitest`

## 10. Тестовые уровни по модулям

### `services/ingestion.py`

- unit tests for normalization
- unit tests for noise filtering decisions
- component tests for event persistence

### `services/retrieval.py`

- unit tests for ranking and space selection
- golden tests for brief assembly
- integration tests against real DB state

### `services/consolidation.py`

- unit tests for merge/supersede rules
- integration tests with `mem0-core` adapter stub
- regression tests for repeated-episode compression

### `services/lifecycle.py`

- deterministic clock-based tests
- eviction and decay tests
- archive boundary tests

### `workers/handlers/*`

- job idempotency tests
- retry behavior tests
- dead-letter / failure handling tests

## 11. Release quality gates

Каждый merge в основную ветку для `memory-runtime` должен проходить минимум следующие проверки:

1. `format`
2. `lint`
3. `unit tests`
4. `component tests`
5. `integration tests`
6. `coverage thresholds`
7. `migration smoke test`
8. `golden regression suite`

Для релизного кандидата дополнительно:

1. `e2e docker scenario`
2. `shared namespace scenario`
3. `isolated namespace leakage check`
4. `worker retry / failure recovery scenario`

## 12. Coverage policy

Не цель гнаться за косметической цифрой ради цифры, но нужны жесткие нижние пороги.

Предлагаемый baseline:

- `unit + component overall`: не ниже `85%`
- `services/retrieval.py`: не ниже `90%`
- `services/consolidation.py`: не ниже `90%`
- `services/lifecycle.py`: не ниже `90%`
- `routers/*`: не ниже `80%`

Важно:

- golden tests и integration tests считаются обязательными дополнениями к coverage
- высокий coverage без scenario/regression tests не считается достаточным

## 13. Правила написания тестов

### Обязательные правила

- каждый новый сервисный модуль должен иметь unit tests
- каждый новый API endpoint должен иметь component tests
- каждое изменение схемы данных должно иметь migration test
- каждое изменение retrieval/consolidation behavior должно иметь regression test
- каждый баг-фикс по памяти должен сопровождаться тестом, воспроизводящим исходный дефект

### Правила качества тестов

- deterministic first
- no random sleeps
- controllable clocks
- no external network dependency
- no real LLM calls in CI
- LLM behavior только через stubs, fakes или frozen fixtures

## 14. Работа с LLM-зависимыми частями

Это критический пункт для стабильности.

В CI нельзя завязываться на реальные LLM ответы.

Поэтому:

- все LLM-интеграции должны проходить через адаптер
- в тестах используются stubbed responses
- для consolidation/retrieval quality используем golden fixtures
- отдельные manual evals можно держать вне обязательного CI

Разделение:

- `CI suite`: deterministic, offline, repeatable
- `manual/benchmark suite`: quality exploration, не блокирует каждый PR

## 15. Data fixtures strategy

Нужен набор стабильных test fixtures по типовым сценариям:

- long-running project discussion
- noisy chat with low-value acknowledgements
- repeated architecture decisions
- cross-agent shared memory
- stale session context
- conflicting updates

Эти фикстуры должны жить в репозитории и переиспользоваться across unit/integration/regression tests.

## 16. CI/CD рекомендации

Для нового сервиса стоит ввести отдельный pipeline, который:

- поднимает Postgres и Redis
- выполняет миграции
- запускает unit/component/integration suites
- сохраняет coverage report
- прогоняет golden regression suite

На этапе релиз-кандидата:

- собирает Docker image
- поднимает compose stack
- прогоняет e2e smoke suite

## 17. Документационная дисциплина

Пользовательская договоренность для проекта:

- после каждого этапа документация обновляется
- при изменении кода он покрывается тестами
- тестовая система развивается как часть архитектуры

Следствие для практики:

- любой архитектурный шаг должен сопровождаться обновлением docs
- любой кодовый шаг без тестов считается незавершенным
- тестовая стратегия должна обновляться при появлении новых рисков

## 18. Следующий практический шаг

После этого плана следующим шагом нужно переходить к scaffold-реализации:

1. создать каталог `memory-runtime`
2. поднять базовый FastAPI app
3. описать конфиг и Docker Compose
4. сразу добавить первую test harness
5. реализовать `healthz`
6. только затем двигаться к namespaces и events

## 19. Definition of Done для scaffold этапа

Scaffold этап считается завершенным, если:

- `memory-runtime` существует как отдельный сервис
- сервис поднимается локально
- есть `README.md`
- есть Dockerfile и compose
- есть базовые настройки тестов
- есть unit/component smoke tests
- документация обновлена

## 20. Следующий артефакт

После этого документа можно переходить к непосредственной реализации scaffold и параллельно зафиксировать:

- `ADR-001` separation from `mem0-core`
- `ADR-002` storage baseline
- `ADR-003` testing and release quality policy
