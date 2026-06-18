---
status: pending
title: Agendador interno do governance-worker
type: backend
complexity: medium
dependencies:
  - task_02
  - task_05
---

# Agendador interno do governance-worker

## Visão Geral
Adiciona o papel agendador ao `governance-worker`: um loop temporal que, conforme a política efetiva e a última execução registrada, enfileira os jobs vencidos (`dedup`, `ttl_prune`, `consolidate`, `purge`) na fila de governança. Roda como singleton para evitar enfileiramento duplicado.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O agendador DEVE consultar `resolve_policy` e `governance_schedule` para determinar quais jobs estão "vencidos" por escopo.
- Jobs vencidos DEVEM ser enfileirados via `governance_queue` e o `last_run_at` correspondente atualizado.
- O agendamento DEVE ser idempotente: reexecuções no mesmo período não duplicam jobs (graças a `governance_schedule`).
- O papel agendador DEVE ser projetado para rodar como singleton (`replicas: 1`).
- O agendador DEVE respeitar uma janela "fora de pico" configurável antes de enfileirar.
</requirements>

## Subtarefas
- [ ] 6.1 Implementar a leitura da agenda efetiva (política + `governance_schedule`) por escopo.
- [ ] 6.2 Implementar a decisão de "vencido" por tipo de job e janela fora de pico.
- [ ] 6.3 Enfileirar jobs vencidos e atualizar `last_run_at` atomicamente.
- [ ] 6.4 Integrar o papel agendador ao loop do `governance-worker` (separável do processador).
- [ ] 6.5 Garantir idempotência de agenda em reexecução no mesmo período.

## Detalhes de Implementação
Ver seções "Arquitetura do Sistema" (papel agendador) e "Fluxo de dados" do TechSpec e o [ADR-002](adrs/adr-002.md). Estende `workers/governance_worker.py` (task_05) consumindo `resolve_policy` (task_02) e a tabela `governance_schedule` (task_01).

### Arquivos Relevantes
- `openmemory/api/app/workers/governance_worker.py` — adicionar papel agendador.
- `openmemory/api/app/utils/governance_policy.py` — `resolve_policy` (agendas).
- `openmemory/api/app/models.py` — `governance_schedule`, `governance_jobs`.
- `openmemory/api/app/utils/governance_queue.py` — `enqueue`.

### Arquivos Dependentes
- `openmemory/docker-stack.yml` — agendador com `replicas: 1` (task_13).
- `openmemory/api/app/utils/metrics.py` — `governance_job_queue_depth` (task_12).

### ADRs Relacionados
- [ADR-002: Worker de governança dedicado com loop temporal interno sobre fila PostgreSQL](adrs/adr-002.md) — define agendador singleton + idempotência via `governance_schedule`.

## Entregáveis
- Papel agendador integrado ao `governance-worker`.
- Lógica de "vencido" + atualização de `governance_schedule`.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de enfileiramento agendado **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Job cuja agenda venceu é enfileirado; job dentro do intervalo não é.
  - [ ] `last_run_at` é atualizado ao enfileirar.
  - [ ] Reexecução no mesmo período não enfileira o mesmo job de novo.
  - [ ] Fora da janela "fora de pico", nada é enfileirado.
  - [ ] Escopo por projeto respeita o override de agenda do projeto.
- Testes de integração:
  - [ ] Ciclo agendador→fila: jobs vencidos aparecem em `governance_jobs` e são consumíveis pelo processador.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Sem enfileiramento duplicado em reexecução
- Agenda respeita política global e overrides por projeto
