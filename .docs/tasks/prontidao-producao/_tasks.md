# Prontidão para produção do OpenMemory — Lista de Tarefas

## Tarefas

| # | Título | Status | Complexidade | Dependências |
|---|--------|--------|--------------|--------------|
| 01 | Gate de CI: workflow openmemory-api-ci + wiring no ci-gate.yml | pending | medium | — |
| 02 | MinIO + rotina de backup (snapshot Qdrant + pg_dump → bucket) | pending | high | task_01 |
| 03 | Endpoints /admin/backup/* + restauração + drill documentado | pending | medium | task_02 |
| 04 | Migration de modelos: enum enforce_quota/cold_tier, Project.last_activity_at, intervalo monthly | pending | medium | task_01 |
| 05 | Política de governança estendida: max_memories, max_memories_action, cold_tier_idle_days | pending | low | task_04 |
| 06 | Handler enforce_quota + registro no dispatcher + métricas | pending | medium | task_04, task_05 |
| 07 | Handler cold_tier (snapshot + remoção reversível) + dispatcher + métricas | pending | high | task_02, task_05 |
| 08 | Instrumentação OpenTelemetry + Collector + backend de traces | pending | high | task_01 |
| 09 | Regras de alerta Prometheus (+ Alertmanager opcional) | pending | medium | task_06, task_07, task_08 |
| 10 | Middleware de rate limit por project+hostname (Redis sliding-window) | pending | medium | task_01 |
| 11 | Middleware de auth por equipe + Docker secrets (modo warn→enforce) | pending | high | task_10 |
| 12 | Documentação: atualizar seção 15 da arquitetura + runbooks | pending | low | task_03, task_06, task_07, task_09, task_11 |

## Fases

- **Fase 1 — Rede de segurança**: task_01, task_02, task_03
- **Fase 2 — Qualidade + operabilidade**: task_04, task_05, task_06, task_07, task_08, task_09
- **Fase 3 — Endurecimento leve**: task_10, task_11
- **Transversal**: task_12
