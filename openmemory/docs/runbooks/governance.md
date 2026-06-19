# Runbook — Governança de memória (quota e cold tier)

> Prontidão para produção, task_05/06/07 — ADR-005, ADR-003.

A governança roda no **governance-worker** (scheduler interno, janela off-peak).
Políticas são resolvidas como **global + override por project**.

## Janela off-peak (parada obrigatória)

O processamento "inteligente" (consolidação/dream, dedup, ttl, quota, cold tier —
todos com chamadas de LLM/varredura) só ocorre dentro da janela `off_peak_hours_utc`.

| Campo / env | Default | Efeito |
|-------------|---------|--------|
| `off_peak_hours_utc` (policy) | `[2, 3, 4, 5]` | Horas **UTC** em que a governança pode rodar. Default = **23:00–02:59 (BRT, UTC−3)**. |
| `GOVERNANCE_ENFORCE_OFF_PEAK` | `true` | Liga a parada obrigatória no **processador**. `false` = drena a fila 24/7 (comportamento antigo). |
| `GOVERNANCE_ENABLE_SCHEDULER` | `true` | Liga o **agendador** (enfileiramento de jobs vencidos). |

Comportamento (start/stop/“acordar”):
- **Entra na janela** → o agendador enfileira jobs vencidos e o processador os drena.
- **Sai da janela** → o agendador para de enfileirar **e** o processador para de puxar
  jobs **agendados**. Jobs **em voo terminam** (não há interrupção no meio de um item, mas cada
  job é limitado por `batch_limit`); jobs agendados ainda na fila **aguardam a próxima janela** (noite seguinte).
- A checagem da janela é em UTC — ajuste `off_peak_hours_utc` ao fuso desejado.

> ℹ️ Jobs **forçados manualmente** (`/admin/governance/jobs/...`, marcados com
> `payload.manual`) **furam o curfew**: rodam imediatamente, a qualquer horário. Só os
> jobs **agendados** respeitam a janela. Útil para troubleshooting sem precisar mexer em env.

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
- Jobs respeitam `batch_limit` e a janela `off_peak_hours_utc` (parada obrigatória no
  processador via `GOVERNANCE_ENFORCE_OFF_PEAK`; ver seção "Janela off-peak").
