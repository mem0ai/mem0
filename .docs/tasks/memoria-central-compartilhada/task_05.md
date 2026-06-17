---
status: completed
title: Fila de escrita persistente (tabela SQLite + WriteQueue)
type: backend
complexity: medium
dependencies: []
---

# Fila de escrita persistente (tabela SQLite + WriteQueue)

## Visão Geral
Implementar a fila de escrita persistente que desacopla o agente da extração por LLM. Uma tabela SQLite e uma implementação `WriteQueue` (enqueue/dequeue/mark_done/mark_failed/depth) guardam os jobs de escrita de forma durável, sobrevivendo a reinícios.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir uma tabela `write_queue` com `id`, `project`, `hostname`, `client_name`, `text`, `status`, `error`, `created_at`, `updated_at`.
- A `WriteQueue` DEVE expor `enqueue`, `dequeue`, `mark_done`, `mark_failed` e `depth`, conforme a interface do TechSpec.
- A fila DEVE ser persistente (sobreviver a reinício do processo).
- `enqueue` DEVE retornar um identificador de rastreio (`job_id`).
- Os estados de job DEVEM ser: `queued`, `processing`, `done`, `failed`.
</requirements>

## Subtarefas
- [ ] 05.1 Definir a tabela `write_queue` e sua migração.
- [ ] 05.2 Implementar `WriteQueue` com enqueue/dequeue/mark_done/mark_failed/depth.
- [ ] 05.3 Garantir persistência e transições de estado consistentes.
- [ ] 05.4 Cobrir com testes o ciclo de vida do job e a persistência.

## Detalhes de Implementação
Seguir a interface descrita em "Design de Implementação → Interfaces Principais" do TechSpec (não duplicar o código aqui). Persistir preferencialmente no SQLite já usado pelo projeto, seguindo o padrão de `mem0/memory/storage.py` (SQLiteManager com lock) ou o DB do OpenMemory (`database.py` + Alembic). A escolha do local de persistência deve ser consistente com onde o worker (tarefa 06) e o `add_memories` (tarefa 07) acessam a fila.

### Arquivos Relevantes
- `openmemory/api/app/models.py` / `openmemory/api/alembic/versions/` — tabela `write_queue` (se no DB do OpenMemory).
- `mem0/memory/storage.py` — padrão de SQLiteManager thread-safe a espelhar.

### Arquivos Dependentes
- Tarefa 06 — worker consome via `dequeue`/`mark_done`/`mark_failed`.
- Tarefa 07 — `add_memories` usa `enqueue`.

### ADRs Relacionados
- [ADR-004: Fila interna de escrita com extração por LLM assíncrona](../adrs/adr-004.md) — Persistência e estados da fila.

## Entregáveis
- Tabela `write_queue` + migração.
- Implementação `WriteQueue` persistente com os métodos definidos.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para persistência da fila **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `enqueue` cria job com status `queued` e retorna `job_id`.
  - [ ] `dequeue` retorna jobs `queued` e os marca `processing`.
  - [ ] `mark_done` transiciona para `done`; `mark_failed` registra `error` e status `failed`.
  - [ ] `depth` reflete a quantidade de itens pendentes.
- Testes de integração:
  - [ ] Após reiniciar (nova conexão ao mesmo arquivo), jobs `queued` permanecem disponíveis.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Fila durável com transições de estado corretas
- `job_id` retornado no enqueue
