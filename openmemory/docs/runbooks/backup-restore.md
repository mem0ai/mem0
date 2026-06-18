# Runbook — Backup e Restauração (drill)

> Prontidão para produção, task_02/task_03 — ADR-003. Alvo LAN single-node.
> Objetivo de recuperação: **RPO ≤ 24h**, **RTO ≤ 1h**.

## Componentes

- **MinIO** (object store S3-compatível) — destino dos backups. Serviço `minio` em `compose/backup.yml`.
- **Rotina de backup** — `app.scripts.run_backup` (serviço `backup`, profile `backup`), snapshot nativo do Qdrant + `pg_dump` do PostgreSQL.
- **Endpoints** — `POST /admin/backup/run`, `GET /admin/backup/status`, `POST /admin/backup/restore`.

Convenção de chave no bucket:
```
backups/{YYYY-MM-DD}/qdrant/{collection}.snapshot
backups/{YYYY-MM-DD}/postgres/dump.sql.gz
```

## Variáveis de ambiente

| Variável | Descrição | Default |
|----------|-----------|---------|
| `S3_ENDPOINT` | URL do MinIO/S3 | `http://minio:9000` |
| `S3_BUCKET` | Bucket de backups | `mem0-backups` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Credenciais | `minioadmin` (trocar) |
| `QDRANT_HOST` / `QDRANT_PORT` | Qdrant | `mem0_store` / `6333` |
| `DATABASE_URL` | PostgreSQL | — |

## Backup agendado

Agende um cron diário (ou via orquestrador) que execute:
```bash
docker compose --profile backup run --rm backup
```
Verifique `GET /admin/backup/status` — `rpo_age_seconds` deve ficar abaixo de 86400 (24h). O alerta `backup_age_seconds > 24h` (task_09) cobre violação de RPO.

## Drill de restauração (executar periodicamente)

1. **Pré-condição**: anote `GET /admin/backup/status` (último backup, idade).
2. **Marque o tempo de início** (para medir o RTO).
3. **Suba um ambiente de restauração** (não o de produção) com o mesmo `DATABASE_URL`/Qdrant alvo.
4. **Dispare a restauração** do prefixo mais recente:
   ```bash
   curl -X POST localhost:8765/admin/backup/restore \
     -H 'content-type: application/json' \
     -d '{"key_prefix":"backups/2026-06-18"}'
   ```
   - Prefixo inexistente retorna **404** (verifique antes em `status`).
   - A ordem é PostgreSQL → Qdrant (metadados antes dos vetores).
5. **Valide**:
   - Contagem de memórias por coleção no Qdrant confere com a origem.
   - `GET /health` retorna `healthy`.
   - Uma busca conhecida (`search_memory`) retorna os resultados esperados.
6. **Marque o tempo de fim** e registre **RTO** (alvo ≤ 1h) e **RPO** (idade do backup usado, alvo ≤ 24h).

## Registro do último drill

| Data | RPO medido | RTO medido | Resultado |
|------|------------|------------|-----------|
| _preencher após o primeiro drill em ambiente real_ | | | |

> O drill exige MinIO + Qdrant + PostgreSQL reais; a orquestração de backup/restore
> é coberta por testes unitários (mocks) em `tests/test_backup.py` e
> `tests/test_backup_endpoints.py`, mas a medição de RTO/RPO só é válida em execução real.
