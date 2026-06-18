---
status: pending
title: Fila de governança + esqueleto do governance-worker
type: backend
complexity: high
dependencies:
  - task_01
---

# Fila de governança + esqueleto do governance-worker

## Visão Geral
Cria a infraestrutura de execução dos jobs de governança: a fila durável em PostgreSQL (`governance_jobs`) e o esqueleto do serviço `governance-worker` no papel processador — dequeue com `FOR UPDATE SKIP LOCKED`, processamento concorrente limitado, idempotência e backoff. É o arcabouço onde os jobs concretos (dedup/TTL/consolidação/purge) serão plugados.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir uma fila `governance_queue` com `enqueue(job)` e `dequeue(limit)` sobre `governance_jobs`, usando `FOR UPDATE SKIP LOCKED` para segurança multi-worker.
- O `governance-worker` DEVE expor `process_once()` para processar um lote (testável isoladamente) e um loop de execução.
- O processamento DEVE ser idempotente por job e aplicar backoff até `max_attempts`, marcando `done`/`failed`.
- Uma falha isolada em um job NÃO DEVE abortar o lote inteiro.
- DEVE haver um entrypoint executável (`python -m app.workers.governance_worker`) seguindo o padrão dos workers existentes.
- O worker DEVE despachar por `job_type` para handlers (registrados pelas tasks 07–10) via um ponto de extensão.
</requirements>

## Subtarefas
- [ ] 5.1 Implementar `governance_queue` (enqueue/dequeue com `SKIP LOCKED`) espelhando `write_queue`.
- [ ] 5.2 Implementar o esqueleto `GovernanceWorker` com `process_once()` e loop.
- [ ] 5.3 Implementar despacho por `job_type` para handlers plugáveis (registro vazio nesta task).
- [ ] 5.4 Implementar retry/backoff e marcação de `done`/`failed` com `attempts`.
- [ ] 5.5 Adicionar o entrypoint `python -m app.workers.governance_worker`.

## Detalhes de Implementação
Ver seções "Arquitetura do Sistema" e "Design de Implementação" do TechSpec e o [ADR-002](adrs/adr-002.md). Espelhar `write_queue.py` e `WriteWorker` (estrutura, constantes, `process_once`); reutilizar o padrão de `workers/__main__.py` para sinais/entrypoint.

### Arquivos Relevantes
- `openmemory/api/app/utils/governance_queue.py` — **novo**: `GovernanceJob`, `GovernanceQueue`.
- `openmemory/api/app/workers/governance_worker.py` — **novo**: `GovernanceWorker` (processador + despacho).
- `openmemory/api/app/utils/write_queue.py` — padrão de fila a espelhar.
- `openmemory/api/app/workers/write_worker.py` — padrão de worker (`process_once`, semáforo, backoff).
- `openmemory/api/app/workers/__main__.py` — padrão de entrypoint/sinais.

### Arquivos Dependentes
- `openmemory/api/app/workers/governance_worker.py` — handlers concretos plugados nas tasks 07–10.
- `openmemory/docker-stack.yml` — serviço de deploy (task_13).

### ADRs Relacionados
- [ADR-002: Worker de governança dedicado com loop temporal interno sobre fila PostgreSQL](adrs/adr-002.md) — define o padrão fila+worker e idempotência.

## Entregáveis
- Módulo `governance_queue.py` (enqueue/dequeue `SKIP LOCKED`).
- `GovernanceWorker` com `process_once`, despacho por tipo, retry/backoff e entrypoint.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de enfileiramento/consumo concorrente **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `enqueue` cria job `queued`; `dequeue(limit)` retorna na ordem FIFO e marca `processing`.
  - [ ] `process_once` processa um lote e marca `done` nos jobs bem-sucedidos.
  - [ ] Job que lança exceção é marcado `failed`/reenfileirado com `attempts` incrementado até `max_attempts`.
  - [ ] Falha de um job não impede o processamento dos demais do lote.
  - [ ] Despacho roteia o `job_type` para o handler registrado (handler fake).
- Testes de integração:
  - [ ] Dois workers consumindo a mesma fila não processam o mesmo job (`SKIP LOCKED`).
  - [ ] Entrypoint inicia e encerra de forma limpa em SIGINT/SIGTERM.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Consumo concorrente seguro (sem processamento duplicado)
- Arcabouço pronto para plugar os jobs das tasks 07–10
