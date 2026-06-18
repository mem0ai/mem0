# Runbook — Diagnóstico de incidente

> Prontidão para produção, task_08/09 — ADR-004. Usa alertas Prometheus + traces OTel.

## Fluxo geral

1. **Alerta dispara** (Prometheus/Alertmanager). Identifique qual (abaixo).
2. **Confirme no Grafana** o sintoma (latência, fila, erros).
3. **Abra o trace** da requisição lenta/falha no Tempo, correlacionando pelo
   `trace_id` que aparece nos logs estruturados (campo `trace_id`).
4. **Siga a ação** correspondente.

## Alertas → ação

### `SearchLatencyP99High` (p99 busca > 500ms por 10m)
- Verifique `embed_cache_hit_total` vs `embed_cache_miss_total` (cache frio?).
- No trace, veja qual span domina: `embed`, `qdrant.search` ou rede.
- Ações: aquecer cache, checar saúde do Qdrant/Ollama (`/health`).

### `WriteQueueBacklog` (`write_queue_depth > 100` por 10m)
- Workers de escrita não acompanham. Veja `write_worker_error_total`.
- Ações: aumentar `WRITE_WORKER_MAX_CONCURRENCY` / nº de réplicas do write-worker;
  checar o LLM de extração (Ollama) no trace.

### `GovernanceJobErrors` / `WriteWorkerErrorRate`
- Inspecione logs filtrando por `job_id`/`request_id`.
- Ações: corrigir causa; jobs têm retry com backoff (`max_attempts`).

### `BackupRPOViolated` (sem backup há > 24h)
- A rotina de backup falhou ou não rodou. Veja `backup_errors_total`.
- Ações: rodar `POST /admin/backup/run`; checar MinIO e credenciais S3; ver
  [runbook de backup](backup-restore.md).

### `ProjectOverSizeThreshold`
- Algum project passou do limite. Veja `GET /admin/projects/sizes`.
- Ações: promover a shard dedicado (`/admin/projects/{name}/promote`) ou definir
  `max_memories`/`enforce` (ver [governança](governance.md)).

## Correlação log ↔ trace

Os logs trazem `request_id`, `job_id` e `trace_id`. Para uma requisição MCP lenta,
copie o `trace_id` do log e abra no Tempo para ver a cadeia
`mcp → embed → qdrant → (escrita) llm`.

## Saúde rápida

```bash
curl localhost:8765/health     # database, qdrant, memory client, fila
curl localhost:8765/metrics    # métricas Prometheus
```
