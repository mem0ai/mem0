---
status: pending
title: Dequeue seguro com FOR UPDATE SKIP LOCKED e concorrência configurável
type: backend
complexity: medium
dependencies:
  - task_01
---

# Dequeue seguro com FOR UPDATE SKIP LOCKED e concorrência configurável

## Visão Geral
Torna o `dequeue` da fila de escrita seguro para múltiplos workers concorrentes usando `SELECT ... FOR UPDATE SKIP LOCKED` no PostgreSQL, garantindo que cada job seja entregue a um único worker. Também expõe a concorrência do worker via configuração, removendo o limite fixo atual.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O `dequeue` DEVE usar `with_for_update(skip_locked=True)` dentro de transação, de modo que dois workers concorrentes NUNCA recebam o mesmo job.
- Em SQLite o comportamento DEVE permanecer funcional (o lock é no-op), preservando o modo dev.
- A ordenação FIFO por `created_at` e o índice `idx_write_queue_status_created` DEVEM ser mantidos.
- `max_concurrency` (e demais parâmetros do worker) DEVE ser configurável via variável de ambiente, sem valor fixo no código.
- Nenhum job DEVE ser perdido ou duplicado sob concorrência.
</requirements>

## Subtarefas
- [ ] 2.1 Alterar o `dequeue` para aplicar `FOR UPDATE SKIP LOCKED` na seleção de jobs `queued`.
- [ ] 2.2 Garantir que a transição para `processing` ocorra na mesma transação do lock.
- [ ] 2.3 Expor `max_concurrency` (e batch/idle/attempts) via env, mantendo defaults atuais como fallback.
- [ ] 2.4 Validar que SQLite continua operando (lock ignorado) sem regressão.

## Detalhes de Implementação
Ver seção "Interfaces Principais" do TechSpec (assinatura do `dequeue`). A mudança é localizada na camada de fila e na parametrização do worker; não altera o contrato MCP nem o modelo de dados.

### Arquivos Relevantes
- `openmemory/api/app/utils/write_queue.py` — `dequeue`/transições de status; adicionar `with_for_update(skip_locked=True)`.
- `openmemory/api/app/workers/write_worker.py` — ler `max_concurrency`/batch/attempts de env.

### Arquivos Dependentes
- `openmemory/api/app/models.py` — `WriteQueueJob`/índice usado na seleção ordenada.

### ADRs Relacionados
- [ADR-003: Fila durável em PostgreSQL com FOR UPDATE SKIP LOCKED e workers em processo separado](../adrs/adr-003.md) — Define o dequeue seguro e a concorrência configurável.

## Entregáveis
- `dequeue` com `SKIP LOCKED` ativo em PostgreSQL e inócuo em SQLite.
- Parâmetros do worker configuráveis por env.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de concorrência **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `dequeue(limit=N)` retorna no máximo N jobs e os marca `processing` na mesma transação.
  - [ ] `max_concurrency` lido de env sobrescreve o default; ausência usa o default.
  - [ ] Ordenação FIFO por `created_at` preservada.
- Testes de integração:
  - [ ] Dois consumidores concorrentes contra PostgreSQL não recebem o mesmo job (nenhuma duplicação).
  - [ ] Sob falha de um consumidor, jobs não confirmados voltam a ser elegíveis (sem perda).
  - [ ] Em SQLite o dequeue funciona sem erro (lock no-op).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Entrega única de jobs comprovada sob concorrência real em PostgreSQL.
- Concorrência do worker ajustável sem alteração de código.
