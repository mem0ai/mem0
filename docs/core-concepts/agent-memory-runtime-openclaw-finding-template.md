# Agent Memory Runtime: OpenClaw Finding Template

Шаблон для одного конкретного finding после pilot-прогона.

## Finding

- `id:`
- `title:`
- `date:`
- `reported by:`
- `scenario:`
- `severity:` `p0 / p1 / p2 / p3`
- `type:` `recall_quality / consolidation / lifecycle / adapter / worker / observability / docs / ops`

## Expected Vs Actual

- `expected behavior:`
- `actual behavior:`
- `why this matters:`

## Evidence

- `query / action that triggered it:`
- `memory brief excerpt:`
- `trace excerpt:`
- `observability / metrics evidence:`
- `logs or API responses:`

## Repro

- `reproducible:` `yes / no / unknown`
- `repro steps:`
- `known scope:` `isolated / shared / both / unknown`

## Suspected Layer

- `ingestion`
- `episode formation`
- `consolidation`
- `retrieval selection`
- `brief packing`
- `adapter contract`
- `worker / jobs`
- `lifecycle`
- `operational environment`

## Initial Hypothesis

- `suspected cause:`
- `confidence:` `low / medium / high`
- `possible fix direction:`

## Backlog Mapping

- `should create backlog item:` `yes / no`
- `suggested priority:`
- `owner:`
- `follow-up notes:`
