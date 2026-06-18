---
status: pending
title: Motor de quarentena/lifecycle (QuarantineEngine)
type: backend
complexity: high
dependencies:
  - task_01
  - task_03
---

# Motor de quarentena/lifecycle (QuarantineEngine)

## Visão Geral
Implementa o ponto único de todas as transições destrutivas reversíveis da governança: colocar memórias em quarentena (preservando o vetor no Qdrant), reverter para `active` e expurgar definitivamente após a janela. Protege memórias pinadas e registra tudo na trilha de auditoria.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE expor as operações da seção "Interfaces Principais" do TechSpec: `quarantine`, `revert`, `purge_expired`.
- `quarantine` DEVE marcar `state=quarantined` na linha SQL (`quarantined_at`, motivo e `job_id` na metadata) e no payload Qdrant, mantendo o vetor.
- `quarantine` NÃO DEVE tocar memórias com `metadata.pinned == true` (retorna indicação de "pulada").
- `revert` DEVE restaurar `quarantined → active` em SQL e payload, sem reembedar.
- `purge_expired` DEVE remover (hard-delete vetor + linha) apenas memórias `quarantined` com `quarantined_at` além da janela.
- Toda transição DEVE gravar `MemoryStatusHistory` com a identidade do job.
</requirements>

## Subtarefas
- [ ] 4.1 Implementar `quarantine(memory_id, reason, job_id)` com proteção de pinadas e dupla escrita (SQL + payload).
- [ ] 4.2 Implementar `revert(memory_id)` restaurando estado em SQL e payload.
- [ ] 4.3 Implementar `purge_expired(older_than_days, limit)` com hard-delete idempotente.
- [ ] 4.4 Registrar `MemoryStatusHistory` em todas as transições.
- [ ] 4.5 Garantir idempotência (reexecutar quarantine/revert/purge não corrompe estado).

## Detalhes de Implementação
Ver seções "Interfaces Principais" e "Fluxo de dados" do TechSpec e o [ADR-003](adrs/adr-003.md). Novo módulo `openmemory/api/app/utils/quarantine.py`. Reaproveitar a lógica de transição de `update_memory_state` (`routers/memories.py`, ~linhas 37–57) e o hard-delete de `vector_store.delete`.

### Arquivos Relevantes
- `openmemory/api/app/utils/quarantine.py` — **novo**: `QuarantineEngine`.
- `openmemory/api/app/routers/memories.py` — `update_memory_state` (padrão de transição + audit).
- `mem0/vector_stores/qdrant.py` — `update` (payload), `delete` (hard-delete), `get`.
- `openmemory/api/app/models.py` — `Memory`, `MemoryStatusHistory`, estado `quarantined` (task_01).

### Arquivos Dependentes
- `openmemory/api/app/workers/governance_worker.py` — jobs chamam o motor (tasks 07–10).
- `openmemory/api/app/routers/admin.py` — `revert` exposto via endpoint (task_11).

### ADRs Relacionados
- [ADR-003: Estado `quarantined` dedicado com retenção do vetor e expurgo diferido](adrs/adr-003.md) — define semântica de quarentena/reversão/expurgo.
- [ADR-001: Governança automática com rede de segurança](adrs/adr-001.md) — proteção de pinadas e reversibilidade.

## Entregáveis
- Módulo `quarantine.py` com `QuarantineEngine` (quarantine/revert/purge_expired).
- Integração com `MemoryStatusHistory` e payload Qdrant.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração do ciclo quarentena→reversão→expurgo **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `quarantine` de memória pinada retorna "pulada" e não altera estado.
  - [ ] `quarantine` define `state=quarantined`, `quarantined_at`, motivo/`job_id` e atualiza payload.
  - [ ] `revert` retorna memória para `active` em SQL e payload.
  - [ ] `purge_expired` ignora memórias dentro da janela e remove as além dela.
  - [ ] Toda transição grava uma linha em `MemoryStatusHistory`.
  - [ ] Reexecução de `quarantine`/`purge` é idempotente (sem erro/duplicação).
- Testes de integração:
  - [ ] Ciclo: `quarantine` → some da busca (com filtro da task_03) mas vetor permanece → `revert` → volta à busca → `purge_expired` → removida do Qdrant e SQL.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Vetor preservado no Qdrant até o expurgo; pinadas nunca tocadas
- Auditoria completa de todas as transições
