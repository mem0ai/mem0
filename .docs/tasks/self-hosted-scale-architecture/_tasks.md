# Arquitetura self-hosted em escala — Lista de Tarefas

## Tarefas

| # | Título | Status | Complexidade | Dependências |
|---|--------|--------|--------------|--------------|
| 01 | Fundação PostgreSQL + PgBouncer (dialeto condicional e migrations) | done | medium | — |
| 02 | Dequeue seguro com FOR UPDATE SKIP LOCKED e concorrência configurável | done | medium | task_01 |
| 03 | Write worker como processo separado (entrypoint + gate do startup) | done | medium | task_02 |
| 04 | Serviços de inferência dedicados (Ollama/llama.cpp) + config do cliente mem0 | done | medium | — |
| 05 | Cache Redis de embedding e resultado de busca com invalidação por escrita | done | high | task_03, task_04 |
| 06 | Reverse proxy + réplicas (rate limit, circuit breaker, sticky SSE, discovery) | done | high | task_04, task_05 |
| 07 | Observabilidade (/health, /metrics, Prometheus/Grafana) | done | medium | task_03, task_05, task_06 |
| 08 | Stack único + bootstrap automatizado (detecção multi-backend + migração) | done | critical | task_01, task_02, task_03, task_04, task_05, task_06, task_07 |
