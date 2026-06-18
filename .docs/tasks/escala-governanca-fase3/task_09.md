---
status: pending
title: Job de purge (expurgo pós-janela)
type: backend
complexity: low
dependencies:
  - task_04
  - task_05
---

# Job de purge (expurgo pós-janela)

## Visão Geral
Único passo irreversível da governança: um handler que remove definitivamente (hard-delete de vetor no Qdrant + linha SQL) as memórias que estão em quarentena há mais tempo que a janela configurada. Fecha o ciclo da rede de segurança liberando armazenamento.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O handler `purge` DEVE expurgar apenas memórias `quarantined` cujo `quarantined_at` exceda `quarantine_window_days` da política efetiva.
- O expurgo DEVE usar `QuarantineEngine.purge_expired` (hard-delete idempotente).
- Memórias dentro da janela ou em outros estados NÃO DEVEM ser tocadas.
- O job DEVE processar em lotes com teto configurável e registrar a contagem expurgada.
- O job DEVE ser registrado como handler de `job_type=purge`.
</requirements>

## Subtarefas
- [ ] 9.1 Obter `quarantine_window_days` da política efetiva por escopo.
- [ ] 9.2 Selecionar memórias `quarantined` além da janela.
- [ ] 9.3 Expurgar via `QuarantineEngine.purge_expired` em lote com teto.
- [ ] 9.4 Registrar o handler em `job_type=purge` e garantir idempotência.

## Detalhes de Implementação
Ver seção "Sequenciamento de Desenvolvimento" (passo 9) do TechSpec e o [ADR-003](adrs/adr-003.md). Handler fino que delega ao motor da task_04 e lê a política da task_02; plugado no worker da task_05.

### Arquivos Relevantes
- `openmemory/api/app/governance/purge.py` — **novo**: handler do job de purge.
- `openmemory/api/app/utils/quarantine.py` — `purge_expired` (task_04).
- `openmemory/api/app/utils/governance_policy.py` — `quarantine_window_days` (task_02).
- `openmemory/api/app/workers/governance_worker.py` — registro do handler.

### Arquivos Dependentes
- `openmemory/api/app/utils/metrics.py` — `governance_purged_total` (task_12).

### ADRs Relacionados
- [ADR-003: Estado `quarantined` dedicado com retenção do vetor e expurgo diferido](adrs/adr-003.md) — purge é o único passo irreversível, pós-janela.

## Entregáveis
- Handler do job de purge registrado no worker.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de expurgo pós-janela **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Memória `quarantined` além da janela é expurgada (vetor + linha SQL).
  - [ ] Memória `quarantined` dentro da janela NÃO é tocada.
  - [ ] Memória `active`/`archived` nunca é expurgada por este job.
  - [ ] Teto de lote limita o número de expurgos por execução.
  - [ ] Reexecução é idempotente (sem erro ao expurgar já removidas).
- Testes de integração:
  - [ ] Após `quarantine` + avanço do tempo além da janela, o job `purge` remove definitivamente do Qdrant e do SQL.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Expurgo só atinge quarentenadas além da janela
- Idempotência comprovada
