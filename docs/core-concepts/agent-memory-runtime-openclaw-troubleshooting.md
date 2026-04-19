# Agent Memory Runtime: OpenClaw Troubleshooting Cheatsheet

Короткий cheatsheet для живого `OpenClaw -> memory-runtime` пилота.

## Как пользоваться

Сначала определяем симптом, потом смотрим:

- `healthz`
- `observability/stats`
- `metrics`
- последний smoke report
- последний quality-eval report

Полезные команды:

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make show-last-smoke
make show-last-quality-eval
make reset-pilot
```

## Симптом: API не отвечает

Проверить:

- `curl http://localhost:8080/healthz`
- `docker compose ps`
- `docker compose logs memory-api`

Частые причины:

- API контейнер не поднялся
- неверный `.env`
- зависимость от `postgres` или `redis` не прошла readiness

## Симптом: ingestion проходит, но память не консолидируется

Проверить:

- `curl http://localhost:8080/v1/observability/stats`
- `docker compose ps`
- `docker compose logs memory-worker`

Индикаторы:

- `jobs_by_status.pending` растет
- `stalled_running_count` больше `0`
- heartbeat worker отсутствует или устарел

Частые причины:

- worker не поднят
- worker не может подключиться к БД
- job handler падает на конкретном эпизоде

## Симптом: recall бедный или пустой

Проверить:

- `POST /v1/recall`
- `trace.selected_space_types`
- `trace.selected_episode_ids`
- `GET /v1/adapters/openclaw/memories`

Частые причины:

- knowledge сохранилось только в `session-space`
- consolidation еще не успела пройти
- вопрос не попадает в нужный `space`
- quality-eval regression после недавнего изменения retrieval

## Симптом: recall тащит мусор

Проверить:

- `make show-last-quality-eval`
- `MemoryBrief` и `trace`
- long-term `list/search`

Частые причины:

- слишком широкая recall selection
- слабое разделение `session` и `long-term`
- конфликтующие воспоминания не superseded

## Симптом: contradictory memory в long-term

Проверить:

- `GET /v1/adapters/openclaw/memories`
- audit actions по `memory_unit_superseded`

Частые причины:

- contradiction heuristic не распознала один из вариантов формулировки
- конфликт относится к разным `spaces`, а не к одному и тому же

## Симптом: OpenClaw не может подключиться к runtime

Проверить:

- `runtime.baseUrl` в конфиге OpenClaw
- `POST /v1/adapters/openclaw/bootstrap`
- `docker compose logs memory-api`

Частые причины:

- неправильный URL
- runtime недоступен из окружения OpenClaw
- source-system mismatch в adapter contract

## Когда делать reset

`make reset-pilot` полезен, если:

- нужно полностью переиграть pilot на чистом контуре
- накопились старые отчеты и локальные state leftovers
- docker stack зашел в неоднозначное состояние

Что делает reset:

- останавливает compose stack и удаляет volumes
- удаляет локальные smoke/eval reports
- очищает локальный SQLite fallback db, если он появился
- убирает worker heartbeat файл
