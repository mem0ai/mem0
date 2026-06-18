---
status: pending
title: Handler cold_tier (snapshot + remoção reversível) + dispatcher + métricas
type: backend
complexity: high
dependencies:
  - task_02
  - task_05
---

# Tarefa 7: Handler cold_tier (snapshot + remoção reversível) + dispatcher + métricas

## Visão Geral
Implementa o arquivamento de projects inativos: ao detectar um project sem atividade na janela `cold_tier_idle_days`, gera um snapshot do seu escopo no MinIO e remove o acervo quente, de forma reversível por restauração. Fecha o gap D2 da auditoria.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir `run_cold_tier_job(*, project, job_id, limit)` seguindo o contrato `Handler`.
- DEVE qualificar como inativo um project cujo `last_activity_at` excede `cold_tier_idle_days`.
- DEVE gerar snapshot do escopo no bucket (convenção `cold/{project}/{timestamp}`) ANTES de remover o acervo quente.
- A remoção DEVE ser reversível por restauração a partir do snapshot.
- DEVE ser registrado no dispatcher e agendado (ex.: `monthly`) e expor `governance_cold_tier_archived_total`.
</requirements>

## Subtarefas
- [ ] 7.1 Detectar projects inativos pela janela de `last_activity_at`.
- [ ] 7.2 Gerar snapshot do escopo do project no MinIO (reusar rotina da task_02).
- [ ] 7.3 Remover o acervo quente do project somente após snapshot confirmado.
- [ ] 7.4 Implementar a restauração/reidratação de um project arquivado.
- [ ] 7.5 Registrar handler, schedule `monthly` e métrica de arquivamento.

## Detalhes de Implementação
Ver seção "Interfaces Principais" do TechSpec e ADR-003/ADR-005. Reusar o cliente S3/snapshot da task_02. A remoção do acervo quente usa o vector store e o catálogo; manter ordem snapshot→remoção para garantir reversibilidade.

### Arquivos Relevantes
- `openmemory/api/app/governance/cold_tier.py` (novo) — handler.
- `openmemory/scripts/backup.*` — rotina de snapshot (reuso).
- `openmemory/api/app/workers/governance_worker.py` — dispatcher + schedule.
- `openmemory/api/app/utils/metrics.py` — métrica de cold tier.
- `mem0/vector_stores/qdrant.py` — operações de delete por escopo.

### Arquivos Dependentes
- `openmemory/api/tests/test_cold_tier.py` (novo) — testes do handler.

### ADRs Relacionados
- [ADR-003: Backup/restauração e cold tier sobre MinIO](adrs/adr-003.md) — mecanismo de snapshot.
- [ADR-005: max_memories e cold tier como job types no governance-worker existente](adrs/adr-005.md) — job type e reuso.

## Entregáveis
- Handler `cold_tier` registrado e agendado.
- Reidratação de project arquivado funcional.
- Métrica `governance_cold_tier_archived_total`.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Teste de integração arquivar→restaurar **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Project ativo (dentro da janela) não é arquivado.
  - [ ] Snapshot é gerado antes da remoção; se o snapshot falhar, a remoção não ocorre.
  - [ ] Métrica de arquivamento incrementa conforme memórias removidas.
- Testes de integração:
  - [ ] Arquivar um project inativo e restaurá-lo recupera as memórias no Qdrant.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Projects inativos são arquivados e podem ser reidratados sem perda
