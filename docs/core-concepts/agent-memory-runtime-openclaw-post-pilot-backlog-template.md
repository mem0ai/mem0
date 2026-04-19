# Agent Memory Runtime: OpenClaw Post-Pilot Backlog Template

Шаблон для перевода pilot findings в рабочий backlog.

## Pilot Context

- `pilot date:`
- `pilot outcome:` `go / conditional-go / no-go`
- `result document:`

## Backlog Table

| ID | Title | Priority | Layer | Source finding | Reproducible | Next action | Owner |
|---|---|---|---|---|---|---|---|
| `BL-001` |  | `p0/p1/p2/p3` |  |  | `yes/no` |  |  |

## Priority Rules

- `p0`:
  блокирует пилот или делает память опасно/явно некорректной
- `p1`:
  сильно бьет по качеству recall или continuity
- `p2`:
  заметно ухудшает UX/операционку, но не блокирует прогон
- `p3`:
  улучшение качества, удобства или ясности без срочности

## Grouping By Layer

### Retrieval

- `items:`

### Consolidation

- `items:`

### Lifecycle

- `items:`

### Adapters / OpenClaw Contract

- `items:`

### Worker / Observability / Ops

- `items:`

### Documentation / Runbooks

- `items:`

## Recommended Next Sprint Slice

- `must fix before next pilot:`
- `should fix soon after next pilot:`
- `can defer:`

## Validation Plan

- `which scenarios must be rerun after fixes:`
- `which quality-eval checks must stay green:`
- `which metrics / traces should be compared before vs after:`
