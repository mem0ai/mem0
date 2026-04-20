# Agent Memory Runtime: OpenClaw Live Pilot Scorecard Template

Используй этот scorecard сразу после живого прогона, чтобы фиксировать не только впечатления, но и сопоставимые метрики качества.

## Метаданные

- `date:`
- `runtime commit:`
- `openclaw config/version:`
- `operator:`
- `scenario pack used:`

## Как оценивать

Для каждого сценария фиксируем:

- `required_hit`
  `1`, если агент вспомнил обязательный факт / решение / процедуру.
  `0`, если не вспомнил.
- `irrelevant_leak`
  `0`, если лишний контекст не протек.
  `0.5`, если был умеренный шум.
  `1`, если лишний recall явно помешал.
- `continuity_success`
  `1`, если continuity между сессиями сохранилась.
  `0`, если continuity сломалась.
- `usefulness`
  Оценка от `1` до `5`: насколько recall реально помог задаче.
- `compactness`
  Оценка от `1` до `5`: насколько brief был компактным и не раздутым.

## Таблица сценариев

| Scenario | required_hit | irrelevant_leak | continuity_success | usefulness (1-5) | compactness (1-5) | Notes |
|---|---:|---:|---:|---:|---:|---|
| durable architecture decision |  |  |  |  |  |  |
| standing procedure recall |  |  |  |  |  |  |
| active session carryover |  |  |  |  |  |  |
| cross-session continuity |  |  |  |  |  |  |
| negative private-boundary |  |  |  |  |  |  |
| negative session-noise |  |  |  |  |  |  |
| negative low-trust |  |  |  |  |  |  |

## JSON Формат Для Автосуммаризации

Сохрани оценки в JSON вида:

```json
{
  "scenario_results": [
    {
      "id": "durable-architecture-decision",
      "required_hit": 1,
      "irrelevant_leak": 0,
      "continuity_success": 1,
      "usefulness": 5,
      "compactness": 4,
      "notes": "Recall returned the correct architecture decision."
    }
  ]
}
```

Потом можно получить summary так:

```bash
cd /Users/slava/Documents/mem0-src/memory-runtime
make pilot-scorecard INPUT=/path/to/live_scorecard.json
```

## Интерпретация verdict

- `pass`
  Пилот показал сильное качество по обязательным фактам, continuity и отсутствию лишних утечек.
- `attention`
  Пилот в целом полезен, но есть заметные зоны для tuning перед более широким использованием.
- `fail`
  Пилот показал недостаточное качество recall или слишком много нежелательных утечек/потерь continuity.
