# Agent Memory Runtime: OpenClaw Pilot Runbook

Практический runbook для первого `OpenClaw-only` MVP-пилота.

Документ нужен для сценария, где мы:

- поднимаем `memory-runtime` как отдельный Docker-модуль
- подключаем `OpenClaw` через `runtime` mode
- проверяем capture, consolidation, recall и worker lifecycle в одном живом контуре

Связанный артефакт:

- [OpenClaw Pilot Scenarios](./agent-memory-runtime-openclaw-pilot-scenarios.md)
- [OpenClaw Troubleshooting Cheatsheet](./agent-memory-runtime-openclaw-troubleshooting.md)
- [Pilot Result Template](./agent-memory-runtime-openclaw-pilot-result-template.md)
- [Finding Template](./agent-memory-runtime-openclaw-finding-template.md)
- [Post-Pilot Backlog Template](./agent-memory-runtime-openclaw-post-pilot-backlog-template.md)

## Цель пилота

Подтвердить, что `OpenClaw` может использовать `memory-runtime` как внешний memory service и получать continuity между сессиями.

Что должно быть доказано:

- OpenClaw успешно bootstraps runtime scope
- события доходят до `memory-runtime`
- worker консолидирует эпизоды в long-term memory
- новый запуск / новая сессия получает полезный recall
- диагностика проблем возможна через API и метрики

## Состав пилота

Минимальный контур:

- `memory-api`
- `memory-worker`
- `postgres`
- `redis`
- `OpenClaw` с плагином `@mem0/openclaw-mem0` в `runtime` mode

## Быстрый старт

### 1. Поднять memory-runtime

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
cp .env.example .env
docker compose up --build
```

Ожидаемое состояние:

- API доступен на `http://localhost:8080`
- health отвечает на `GET /healthz`
- worker запущен как отдельный контейнер

Примечание:

- при первом старте worker может ждать готовности Postgres несколько секунд и ретраить подключение автоматически

### 2. Проверить runtime руками

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/metrics
curl http://localhost:8080/v1/observability/stats
```

### 3. Настроить OpenClaw plugin

Пример `openclaw.json`:

```json5
"openclaw-mem0": {
  "enabled": true,
  "config": {
    "mode": "runtime",
    "userId": "pilot-user",
    "runtime": {
      "baseUrl": "http://localhost:8080",
      "agentName": "primary"
    }
  }
}
```

## Сценарии приемки

Подробный набор сценариев и ожидаемых исходов вынесен в отдельный документ:

- [OpenClaw Pilot Scenarios](./agent-memory-runtime-openclaw-pilot-scenarios.md)

### Сценарий 1. Bootstrap scope

Проверяем:

- OpenClaw может впервые обратиться к runtime
- namespace и agent scope создаются автоматически

Ожидаемый сигнал:

- `POST /v1/adapters/openclaw/bootstrap` возвращает `namespace_id` и `agent_id`

### Сценарий 2. Durable project memory

Проверяем:

- агент сохраняет важное архитектурное или проектное знание
- worker продвигает его в long-term memory
- память видна через list/search

Ожидаемый сигнал:

- после capture и worker processing запись видна через `GET /v1/adapters/openclaw/memories`

### Сценарий 3. Session carryover

Проверяем:

- агент сохраняет session-scoped рабочий контекст
- тот же session id может получить этот контекст через recall/search

Ожидаемый сигнал:

- `POST /v1/adapters/openclaw/search` с `session_id` возвращает session memory

### Сценарий 4. Cross-session continuity

Проверяем:

- во второй сессии агент вспоминает важное знание из предыдущей работы

Ожидаемый сигнал:

- `POST /v1/adapters/openclaw/recall` возвращает `MemoryBrief` с prior decisions или active project context

## Acceptance Checklist

- `docker compose up --build` поднимает API и worker без ручных фиксов
- `GET /healthz` отвечает `200`
- `GET /metrics` и `GET /v1/observability/stats` доступны
- OpenClaw успешно работает в `runtime` mode
- bootstrap scope создается автоматически
- ingestion через OpenClaw adapter contract работает
- worker обрабатывает consolidation jobs
- long-term memory появляется в list/search
- recall в новой сессии возвращает полезный контекст
- при ошибке есть достаточная диагностика через logs/stats/metrics

## Полезные команды

### Локальный запуск без Docker

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make run
make run-worker
```

### One-shot обработка очереди

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make run-worker-once
```

### E2E smoke для pilot flow

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make test-e2e
```

### Unified preflight check

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make preflight
```

Результат:

- подтверждается доступность `healthz`, `/metrics` и `/v1/observability/stats`
- проверяется worker round-trip на тестовом событии
- проверяется recall round-trip на том же контуре
- JSON report сохраняется в `.artifacts/openclaw_preflight_report.json`

Если preflight возвращает `fail`, это больше не считается "непонятным" состоянием:

- отдельные e2e tests уже проверяют сценарий `API жив, worker не обрабатывает jobs`
- stalled/running degradation отдельно валидируется через `/v1/observability/stats`

### Full synthetic pilot smoke

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make pilot-smoke
```

Результат:

- stack поднимается автоматически
- synthetic OpenClaw flow прогоняется end-to-end
- JSON report сохраняется в `.artifacts/openclaw_pilot_smoke_report.json`

### Automated pilot scenario subset

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make pilot-scenarios
```

Результат:

- автоматизированно прогоняются 5 наиболее важных pilot-сценариев
- JSON report сохраняется в `.artifacts/openclaw_pilot_scenarios_report.json`
- прогон можно использовать как pre-pilot gate до live OpenClaw session

### Recall quality eval report

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make quality-eval
```

Результат:

- golden recall scenarios прогоняются against running runtime
- JSON report сохраняется в `.artifacts/recall_quality_eval_report.json`

### Показать последний smoke report

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make show-last-smoke
```

### Показать последний quality eval report

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make show-last-quality-eval
```

### Сбросить pilot environment

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make reset-pilot
```

### Снять snapshot pilot state

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make snapshot-pilot NAME=before-live
```

Результат:

- SQL dump базы памяти сохраняется в `.artifacts/pilot_snapshots/before-live/memory_runtime.sql`
- observability snapshot сохраняется рядом
- доступные pilot reports копируются в `.artifacts/pilot_snapshots/before-live/reports/`
- manifest сохраняется в `.artifacts/pilot_snapshots/before-live/manifest.json`

### Восстановить snapshot pilot state

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make restore-pilot SNAPSHOT=before-live
```

Результат:

- compose Postgres пересоздает `memory_runtime`
- состояние памяти восстанавливается из SQL dump
- связанные pilot reports возвращаются в `.artifacts/`
- API и worker снова поднимаются на восстановленном состоянии

### Показать доступные snapshots

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make show-pilot-snapshots
```

## Если что-то пошло не так

Сначала проверить:

- `/healthz`
- `/v1/observability/stats`
- `/metrics`
- что worker действительно запущен
- что события создают jobs
- если нужно воспроизвести failure на том же состоянии, восстановить последний подходящий snapshot
- что jobs переходят в `completed`, а не в `failed`

Типовые причины проблем:

- OpenClaw указывает неверный `runtime.baseUrl`
- worker не поднят, поэтому ingestion идет, но консолидация не происходит
- используется session-scoped capture там, где ожидается long-term continuity
- namespace/agent bootstrap не произошел, и adapter contract падает на валидации

Более короткий symptom-driven cheatsheet:

- [OpenClaw Troubleshooting Cheatsheet](./agent-memory-runtime-openclaw-troubleshooting.md)

## Что заполнить после живого пилота

Сразу после прогона полезно заполнить:

- [Pilot Result Template](./agent-memory-runtime-openclaw-pilot-result-template.md)
- [Finding Template](./agent-memory-runtime-openclaw-finding-template.md) для каждого значимого сбоя или неожиданного поведения
- [Post-Pilot Backlog Template](./agent-memory-runtime-openclaw-post-pilot-backlog-template.md) для перевода findings в рабочий план
