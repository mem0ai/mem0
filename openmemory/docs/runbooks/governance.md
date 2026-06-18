# Runbook — Governança de memória (quota e cold tier)

> Prontidão para produção, task_05/06/07 — ADR-005, ADR-003.

A governança roda no **governance-worker** (scheduler interno, janela off-peak).
Políticas são resolvidas como **global + override por project**.

## Políticas relevantes

| Campo | Default | Efeito |
|-------|---------|--------|
| `max_memories` | `null` (sem teto) | Teto de memórias ativas por project. |
| `max_memories_action` | `alert` | `alert` só contabiliza; `enforce` quarentena até o teto. |
| `cold_tier_idle_days` | `180` | Inatividade que qualifica um project para arquivamento. |
| `protected_categories` | `[decision, security]` | Categorias nunca podas/arquivadas. |

Memórias `pinned` e de `protected_categories` nunca são removidas.

## Operações

### Definir teto por project
```bash
curl -X PUT localhost:8765/admin/governance/policies/<project> \
  -H 'content-type: application/json' \
  -d '{"max_memories": 1000000, "max_memories_action": "enforce"}'
```
- Comece com `alert`, observe `governance_quota_over_limit_projects`, depois vire `enforce`.

### Forçar um job manualmente
```bash
curl -X POST localhost:8765/admin/governance/jobs/enforce_quota -d '{"project":"<project>"}'
curl -X POST localhost:8765/admin/governance/jobs/cold_tier     -d '{"project":"<project>"}'
```

### Reverter uma quarentena
```bash
curl -X POST localhost:8765/admin/governance/revert/<memory_id>
```

### Restaurar um project arquivado (cold tier)
O `cold_tier` exporta os pontos para `cold/{project}/{ts}.json` no MinIO **antes** de
remover. Para reidratar, recupere o objeto e reimporte as memórias (script de
restauração / re-add via pipeline de escrita).

## Métricas e alertas

- `governance_quota_enforced_total`, `governance_quota_over_limit_projects`
- `governance_cold_tier_archived_total`
- `governance_pruned_total`, `governance_deduped_total`, `governance_purged_total`
- `governance_job_errors_total` → alerta `GovernanceJobErrors`
- `retrieval_quality_index`, `retrieval_duplicate_in_topk_ratio`

## Cuidados

- `enforce`/cold tier removem dados; ambos são **reversíveis** (quarentena antes do
  purge; export antes do drop). Prefira `alert` até validar os limiares.
- Jobs respeitam `batch_limit` e a janela `off_peak_hours_utc`.
