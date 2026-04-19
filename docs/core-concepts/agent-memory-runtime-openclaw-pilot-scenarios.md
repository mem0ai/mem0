# Agent Memory Runtime: OpenClaw Pilot Scenarios

Набор целевых pilot-сценариев для первого живого прогона `OpenClaw -> memory-runtime`.

Документ нужен, чтобы тестировать память не “на глаз”, а по повторяемым сценариям с понятными критериями прохождения.

## Как использовать этот набор

- каждый сценарий прогоняется на чистом или заранее известном namespace
- после capture даем worker время на consolidation
- для каждого сценария проверяем не только ответ агента, но и evidence в `memory-runtime`
- если сценарий не проходит, фиксируем: что агент вспомнил, что пропустил, что вспомнил лишнего

## Что считаем прохождением

- нужное воспоминание попадает в recall или search
- шум и нерелевантные записи не забивают `MemoryBrief`
- trace и observability позволяют понять, почему именно что-то было выбрано
- поведение воспроизводимо на повторном прогоне

## Scenario 1: Durable Architecture Decision

`Цель:` проверить, что важное архитектурное решение переживает сессию и возвращается как long-term memory.

`Setup:`
- в первой сессии агент формулирует решение: `memory-runtime остается Python-first для v1`
- дополнительно фиксирует stack: `Postgres, Redis, pgvector`

`Recall prompt:`
- `Какие архитектурные решения по memory-runtime уже приняты?`

`Ожидаемое:`
- recall содержит `Python-first`
- recall содержит `Postgres, Redis, pgvector`
- ответ не засорен бытовыми или session-only заметками

`Evidence:`
- `POST /v1/adapters/openclaw/recall`
- `POST /v1/adapters/openclaw/search`
- `GET /v1/adapters/openclaw/memories`

## Scenario 2: Standing Procedure Recall

`Цель:` проверить, что постоянное procedural knowledge не теряется за project-context.

`Setup:`
- агент получает устойчивое правило: `сначала краткое архитектурное summary, потом implementation details`
- рядом добавляется несколько project заметок, чтобы создать конкуренцию

`Recall prompt:`
- `Как агент должен подавать архитектурные апдейты?`

`Ожидаемое:`
- recall возвращает procedural memory про concise summary
- `MemoryBrief` не подменяет правило случайными проектными заметками

`Evidence:`
- `POST /v1/adapters/openclaw/recall`
- `selected_space_types` и `selected_episode_ids` в trace

## Scenario 3: Active Session Carryover

`Цель:` убедиться, что рабочая память текущей сессии быстро доступна без long-term pollution.

`Setup:`
- в активной сессии агент пишет: `сейчас я готовлю pilot acceptance checklist`
- параллельно существуют старые проектные записи

`Recall prompt:`
- `Что я сейчас делаю в этой сессии?`

`Ожидаемое:`
- recall возвращает текущую задачу про `pilot acceptance checklist`
- старые long-term записи не вытесняют active carryover

`Evidence:`
- `POST /v1/adapters/openclaw/recall` с текущим `session_id`
- `POST /v1/adapters/openclaw/search` с текущим `session_id`

## Scenario 4: Cross-Session Continuity

`Цель:` проверить, что новая сессия получает continuity из прошлой работы.

`Setup:`
- в первой сессии агент сохраняет решение или важный progress marker
- запускается новая сессия с другим `session_id`

`Recall prompt:`
- `На чем мы остановились по memory-runtime?`

`Ожидаемое:`
- recall подмешивает prior decisions и active project context из прошлой сессии
- continuity работает даже без точного повторения исходной формулировки

`Evidence:`
- сравнение `trace.selected_space_types` между первой и второй сессией

## Scenario 5: Noise Resistance

`Цель:` убедиться, что нерелевантный шум не попадает в полезный brief.

`Setup:`
- в истории есть мусорные записи вроде `book flights`, `temporary scratch note`, `old deprecated deployment note`
- рядом есть одно-два реально полезных воспоминания

`Recall prompt:`
- `Что важно помнить для текущей архитектурной работы?`

`Ожидаемое:`
- recall не возвращает бытовой шум
- случайные черновики не вытесняют реальные project memories

`Evidence:`
- `MemoryBrief`
- quality-eval или ручная проверка must-not-contain

## Scenario 6: Consolidation Correctness

`Цель:` проверить, что repeated turns схлопываются в устойчивое long-term memory, а не плодят дубли.

`Setup:`
- агент несколько раз в разных сообщениях повторяет одно и то же решение
- worker обрабатывает consolidation jobs

`Recall prompt:`
- `Какие решения по storage stack уже закреплены?`

`Ожидаемое:`
- list/search не показывают каскад одинаковых записей
- long-term слой выглядит как одно устойчивое знание, а не как пачка дублей

`Evidence:`
- `GET /v1/adapters/openclaw/memories`
- observability counters по `consolidation_created_total` и `consolidation_merged_total`

## Scenario 7: Session-vs-Long-Term Boundary

`Цель:` проверить, что рабочие session notes не утекают в durable memory без причины.

`Setup:`
- агент создает временную заметку вроде `позже проверить запасной naming для API`
- одновременно сохраняется одно действительно важное проектное решение

`Recall prompt:`
- `Какие устойчивые знания уже есть по проекту?`

`Ожидаемое:`
- временная заметка не доминирует в long-term list/search
- проектное решение остается доступным

`Evidence:`
- `GET /v1/adapters/openclaw/memories`
- сравнение recall и long-term list

## Scenario 8: Debuggability Under Failure

`Цель:` проверить, что при проблеме можно быстро локализовать неисправность.

`Setup:`
- имитируется один плохой прогон: например, worker остановлен или jobs зависли

`Проверка:`
- можно ли быстро понять, что именно сломалось

`Ожидаемое:`
- `/v1/observability/stats` показывает backlog или stalled jobs
- `/metrics` отражает job/consolidation activity
- из runbook понятно, куда смотреть дальше

## Приоритет на первый живой pilot

Сначала прогоняем 5 наиболее импактных сценариев:

- `Scenario 1: Durable Architecture Decision`
- `Scenario 2: Standing Procedure Recall`
- `Scenario 3: Active Session Carryover`
- `Scenario 4: Cross-Session Continuity`
- `Scenario 5: Noise Resistance`

Если они проходят, MVP уже можно считать жизнеспособным для первого рабочего контура с `OpenClaw`.

## Формат фиксации результатов

Для каждого сценария фиксируем:

- `passed` / `failed`
- что именно агент вспомнил
- что именно не вспомнил
- что вспомнил лишнего
- trace из recall
- observability snapshot, если был operational issue
