# Fase 3: Governança de qualidade da memória — Lista de Tarefas

## Tarefas

| # | Título | Status | Complexidade | Dependências |
|---|--------|--------|--------------|--------------|
| 01 | Modelos e migrations de governança | pending | medium | — |
| 02 | Resolvedor de política efetiva (global + override) | pending | medium | task_01 |
| 03 | Índice de payload `state` no Qdrant + filtro `state=active` na busca | pending | high | task_01 |
| 04 | Motor de quarentena/lifecycle (QuarantineEngine) | pending | high | task_01, task_03 |
| 05 | Fila de governança + esqueleto do governance-worker | pending | high | task_01 |
| 06 | Agendador interno do governance-worker | pending | medium | task_02, task_05 |
| 07 | Job de dedup em lote | pending | medium | task_04, task_05 |
| 08 | Job de poda por TTL (idade e último acesso) | pending | medium | task_02, task_04, task_05 |
| 09 | Job de purge (expurgo pós-janela) | pending | low | task_04, task_05 |
| 10 | Pipeline de consolidação semântica (candidatura + LLM) | pending | high | task_04, task_05 |
| 11 | Endpoints `/admin/governance/*` | pending | medium | task_02, task_04, task_05 |
| 12 | Observabilidade e medição de qualidade | pending | medium | task_03, task_06, task_10 |
| 13 | Deploy do serviço governance-worker | pending | medium | task_06, task_07, task_08, task_09, task_10 |
