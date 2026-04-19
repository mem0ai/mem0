# Agent Memory Runtime v1

Рабочий документ, фиксирующий договоренности, продуктовую постановку и предварительные архитектурные выводы по проекту автономной памяти для агентной работы на базе `mem0`.

## Статус

- Документ создан как стартовая точка для дальнейшего проектирования.
- Решения ниже считаются актуальными, пока не будут явно пересмотрены.
- Горизонт документа: `v1` и ближайшие последующие итерации.

## Контекст

Команда не разрабатывает memory-system с нуля, а берет `mem0` как основу, включая уже сделанные локальные изменения. Цель состоит в том, чтобы построить максимально сильный независимый memory-модуль для агентной работы:

- автономный
- self-hosted
- устанавливаемый через Docker
- со своей БД или несколькими БД при необходимости
- пригодный для интеграции с `OpenClaw` и `BunkerAI`

Ключевая амбиция: не просто хранить воспоминания, а управлять полным жизненным циклом памяти агента:

- работа с контекстом
- компактизация
- границы краткосрочной памяти
- перенос в долгосрочную память
- механизмы извлечения
- забывание и вытеснение
- подмешивание воспоминаний в контекст
- дальнейшее развитие в сторону richer memory architecture

## Зафиксированные решения

### 1. Главный субъект памяти

Главный владелец и пользователь памяти: `агент`.

Это означает, что архитектура проектируется не вокруг "пользователя" как primary entity, а вокруг agent-centric memory model.

### 2. Режимы совместного использования памяти

- Если `OpenClaw` и `BunkerAI` работают в связке, память должна быть `общей`.
- Если они работают независимо, память должна быть `раздельной`.

Отсюда следует требование поддерживать:

- `isolated namespaces`
- `shared namespaces`
- переключение между этими режимами на уровне конфигурации или orchestration layer

### 3. Требования к задержке

Жесткой борьбы за realtime на текущем этапе нет.

Следствие:

- можно допускать более сложный retrieval pipeline
- можно выносить часть консолидации и улучшения памяти в фоновые процессы
- можно оптимизировать прежде всего под качество recall, а не под минимальную latency

### 4. Уровень автономности

Память в первой версии должна быть `полностью автономной`.

Дополнительно зафиксировано пожелание:

- предусмотреть механизмы `auto-improvement`

На текущем этапе не закладывается обязательный human review для переноса воспоминаний в long-term memory.

### 5. Главный приоритет v1

Главный приоритет: `качество`.

Под качеством понимается:

- релевантность recall
- полнота полезного контекста
- минимизация мусора в injected context

Безопасность на этом этапе не является главным драйвером архитектуры v1.

### 6. Модель "чертогов памяти"

Для первой итерации выбрана модель:

- `иерархические memory spaces`

Итеративная дорожная карта:

- `v1`: memory spaces как основа
- `v1.5`: graph layer как усилитель retrieval
- `v2`: производные knowledge dossiers / rooms / curated memory views

## Рабочее определение продукта

Мы строим не просто memory store и не просто vector database wrapper, а `Autonomous Agent Memory Runtime`.

Это отдельный сервис, который:

- принимает события агентной работы
- хранит краткосрочную и долгосрочную память
- самостоятельно решает, что оставить в short-term
- самостоятельно решает, что переносить в long-term
- извлекает релевантные воспоминания под текущую задачу
- подает агенту не сырой поиск, а компактный memory brief
- управляет забыванием, вытеснением, сжатием и обновлением памяти

## Product North Star

Агент должен отвечать и действовать лучше не потому, что ему передали больше текста, а потому, что memory runtime возвращает именно тот контекст, который реально нужен в данный момент.

## Основные сценарии v1

1. Агент продолжает работу спустя часы, дни и недели без потери проектного контекста.
2. Два агента в связке используют общую память без ручной синхронизации.
3. Краткосрочный шум не засоряет долгосрочную память.
4. Повторяющиеся эпизоды консолидируются в устойчивые memory objects.
5. Агент получает в контекст memory brief, а не свалку top-k результатов.
6. Память со временем становится полезнее за счет внутренних сигналов использования.

## Что входит в v1

- текстовая память
- short-term и long-term memory
- memory spaces
- episodic, semantic и procedural memory
- consolidation pipeline
- retrieval orchestration
- forgetting / decay / eviction
- history / audit
- Docker-first deployment

## Что не входит в v1

- полноценный UI для ручной курации памяти
- multimodal memory как core feature
- heavy human moderation flows
- приоритетная оптимизация под very low latency
- сложный security-first perimeter как основной предмет разработки

## Предварительная продуктовая модель памяти

Базовые пространства памяти агента:

### `agent-core`

Постоянные свойства агента:

- устойчивые знания
- правила работы
- роль
- процедурные настройки

### `shared-space`

Общая память нескольких агентов, если `OpenClaw` и `BunkerAI` работают как единая связка.

### `project-space`

Память по проекту, окружению, архитектуре, решениям, инструментам, активным гипотезам и рабочим договоренностям.

### `session-space`

Оперативный контекст текущего run, task или session.

## Жизненный цикл памяти

Целевая схема жизненного цикла:

`event -> episode -> session-space -> compaction -> scored candidates -> long-term storage -> retrieval bundle -> decay / forgetting`

Это означает, что базовой единицей системы становится не просто "сообщение" и не просто "документ", а memory-relevant episode и производные memory units.

## Исследование текущей базы

В рамках первичного изучения репозитория были подтверждены следующие опорные факты.

### Что уже есть в базе `mem0/openclaw`

1. Разделение краткосрочной и долгосрочной памяти уже присутствует в текущей интеграции `OpenClaw`.
2. Есть auto-recall перед ответом агента.
3. Есть auto-capture после завершения агентного прохода.
4. Есть message filtering pipeline для устранения шумовых сообщений до extraction.
5. Есть базовая история изменений памяти через SQLite history DB.
6. Есть graph-memory слой и поддержка Neo4j.
7. Есть поддержка reranking и metadata-aware retrieval.
8. Есть REST API server как точка для language-agnostic интеграций.

### Конкретные подтвержденные наблюдения по коду

#### `openclaw`

- В [openclaw/index.ts](/Users/slava/Documents/mem0-src/openclaw/index.ts:820) реализованы auto-recall и auto-capture lifecycle hooks.
- Там же реализована инъекция recall-результатов в контекст агента и разделение на long-term и session memories.
- В [openclaw/filtering.ts](/Users/slava/Documents/mem0-src/openclaw/filtering.ts:1) уже есть пайплайн предэкстракционной фильтрации:
  - удаление noise messages
  - content stripping
  - отсев generic assistant acknowledgements
  - truncation
- В [openclaw/config.ts](/Users/slava/Documents/mem0-src/openclaw/config.ts:1) уже есть сильные extraction instructions, включая:
  - приоритет durable facts
  - temporal anchoring
  - deduplication
  - outcome-over-intent
  - language preservation
  - исключение секретов из памяти
- В `OpenClaw` уже сделана логика session-vs-long-term scopes и частичная agent isolation.

#### `mem0 core`

- В [mem0/memory/main.py](/Users/slava/Documents/mem0-src/mem0/memory/main.py:1) уже есть основной memory engine, работа с config, embedder, vector store, LLM, history DB и supporting utilities.
- В [mem0/memory/storage.py](/Users/slava/Documents/mem0-src/mem0/memory/storage.py:1) уже есть SQLite history manager с миграцией и аудитом изменений памяти.
- В [mem0/configs/base.py](/Users/slava/Documents/mem0-src/mem0/configs/base.py:1) зафиксированы основные конфигурационные сущности `MemoryConfig` и `MemoryItem`.
- В [mem0/memory/utils.py](/Users/slava/Documents/mem0-src/mem0/memory/utils.py:1) есть вспомогательные функции для extraction prompts, parsing и normalization.

#### `server`

- В [server/docker-compose.yaml](/Users/slava/Documents/mem0-src/server/docker-compose.yaml:1) уже есть self-hosted dev-конфигурация с:
  - API server
  - Postgres / pgvector
  - Neo4j
- В [server/README.md](/Users/slava/Documents/mem0-src/server/README.md:1) подтвержден существующий REST API server для операций с памятью.

#### `openmemory`

- В [openmemory/README.md](/Users/slava/Documents/mem0-src/openmemory/README.md:1) видно, что в репозитории уже есть self-hosted memory-related product contour с Docker setup и MCP/API surface.

### Вывод по текущему состоянию

Текущая база уже содержит сильный `memory engine` и рабочую интеграцию, но пока не является полноценной agent-memory platform.

Главный вывод:

- текущее ядро лучше развивать как `mem0-core`
- новый проект нужно строить как `memory runtime/orchestration layer` поверх него

То есть v1 не должен быть "еще одним плагином", а должен стать отдельным внешним сервисом, который владеет:

- lifecycle management
- memory spaces
- consolidation orchestration
- retrieval orchestration
- shared/isolated namespaces
- forgetting policies

## Целевая архитектурная гипотеза

Рекомендуемая форма системы:

### 1. `Memory Gateway`

Внешний ingress для:

- OpenClaw
- BunkerAI
- будущих интеграций

Поддерживаемые поверхности:

- REST
- MCP
- при необходимости OpenAI-compatible facade

### 2. `Ingestion & Normalization`

Приведение событий к единому internal event model:

- agent
- namespace
- project/workspace
- run/session
- source
- timestamp
- trust/type tags

### 3. `Working Memory Engine`

Обслуживание `session-space`:

- append
- windowing
- TTL
- compaction
- episode segmentation
- локальная deduplication

### 4. `Consolidation Engine`

Фоновый перенос из short-term в long-term:

- extraction
- merge
- update
- contradiction handling
- scoring
- promotion into long-lived spaces

### 5. `Retrieval Orchestrator`

Извлечение должно быть гибридным:

- semantic retrieval
- metadata / symbolic filtering
- recency-sensitive recall
- optional graph-assisted retrieval
- reranking
- context packing into a brief

### 6. `Memory Lifecycle Manager`

Управление жизненным циклом памяти:

- decay
- eviction
- compression
- archival
- promotion / demotion

### 7. `Observability & Audit`

Наблюдаемость и разбор полезности памяти:

- что было сохранено
- что было извлечено
- что было injected в context
- что было забыто
- что дало пользу агенту

## Рекомендованный storage stack для v1

### Базовый состав

- `Postgres` как source of truth
- `pgvector` для semantic retrieval
- `Redis` для очередей и фоновых job'ов

### Опционально

- `Neo4j` как graph enhancement layer

Рекомендация:

- не делать `Neo4j` обязательным компонентом v1
- сначала построить сильный baseline на `Postgres + pgvector + Redis`

## Ключевые доменные сущности

### `MemoryEvent`

Сырой входящий сигнал от агента или интеграции.

### `Episode`

Сегмент рабочей активности, из которого извлекаются кандидаты в память.

### `MemoryUnit`

Базовая единица памяти.

Минимальный набор полей:

- `id`
- `agent_id`
- `namespace_id`
- `space_type`
- `scope`
- `kind`
- `content`
- `summary`
- `importance`
- `confidence`
- `freshness`
- `durability`
- `source_refs`
- `created_at`
- `last_accessed_at`
- `retrieval_count`
- `expires_at`
- `supersedes_id`
- `status`

### `MemorySpace`

Иерархическое пространство памяти.

### `MemoryLink`

Связь между memory units.

### `RecallRequest`

Структурированный запрос на извлечение памяти.

### `MemoryBrief`

Собранный и компактно упакованный пакет памяти для подмешивания в контекст агента.

### `LifecyclePolicy`

Набор правил retention, TTL, forgetting, compression и promotion.

## Целевые принципы retrieval

В v1 retrieval должен уйти от простого `top-k vector search`.

Базовая стратегия:

1. Определить релевантные memory spaces.
2. Поднять кандидатов из:
   - `session-space`
   - `project-space`
   - `agent-core`
   - при необходимости `shared-space`
3. Смешать сигналы:
   - semantic similarity
   - importance
   - freshness
   - prior usefulness
   - project affinity
4. Выполнить rerank.
5. Сформировать `memory brief` в рамках budgeted context packing.

Целевой формат brief:

- critical facts
- active project context
- relevant prior decisions
- standing procedures
- recent session carryover

## Целевые принципы forgetting

В v1 forgetting не должен сводиться к наивному удалению по возрасту.

Нужны как минимум четыре механизма:

1. `TTL`
   Для session-space и прочих short-lived memories.
2. `Decay`
   Ослабление веса старых и бесполезных memories.
3. `Compression`
   Схлопывание повторяющихся эпизодов в более устойчивые memory units.
4. `Eviction / Archive`
   Удаление или выталкивание слабых memories из hot layers.

Ключевой принцип:

- forgetting = управление полезностью, а не только удаление данных

## Роль auto-improvement

Так как пользователь явно запросил полностью автономную память с потенциальным автоулучшением, v1 должен проектироваться так, чтобы позже можно было добавить signals-based optimization.

Базовые сигналы для будущего auto-improvement:

- memory retrieved but unused
- memory retrieved and echoed in output
- memory frequently selected across similar tasks
- memory superseded by newer knowledge
- memory repeatedly compacted into summaries

## Интеграционная гипотеза

### `OpenClaw`

Текущий plugin contour используется как первый реальный интеграционный клиент.

### `BunkerAI`

Для него предполагается аналогичный adapter / connector contour.

Если обе системы работают как единый orchestration cluster:

- они используют общий shared namespace

Если работают независимо:

- каждая использует изолированное memory space tree

## Предварительный план реализации

### Phase 1

Выделить отдельный `memory runtime service`:

- API
- Docker Compose
- Postgres
- pgvector
- Redis
- базовые memory spaces
- history / audit

### Phase 2

Реализовать:

- short-term / long-term split
- consolidation engine
- memory brief builder
- retrieval orchestrator

### Phase 3

Добавить:

- decay
- eviction
- compression
- retention policies

### Phase 4

Подключить:

- shared memory mode
- usefulness signals
- auto-improvement loop

## Главная архитектурная договоренность

Проект не развивается как "очередной плагин к mem0".

Проект развивается как:

- `новый внешний memory runtime`
- использующий `mem0` как базовый memory engine / core

Иначе говоря:

- `mem0` остается ядром хранения, extraction и retrieval primitives
- новый runtime владеет orchestration, lifecycle и agent-centric memory model

## Следующий шаг

Следующим артефактом должен стать `System Design v1`, включающий:

- component diagram
- data flow
- API contract
- storage schema
- queue/job model
- этапы реализации по спринтам
