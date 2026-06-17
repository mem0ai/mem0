---
status: completed
title: Worker de background (consome fila → extração + catálogo)
type: backend
complexity: high
dependencies:
  - task_01
  - task_02
  - task_05
---

# Worker de background (consome fila → extração + catálogo)

## Visão Geral
Implementar o worker assíncrono que consome a fila de escrita, executa a extração por LLM local e persiste a memória no projeto, fazendo o upsert no catálogo. O worker limita a concorrência contra o LLM (protegendo-o de sobrecarga) e trata falhas com retentativa/log, sem o agente presente.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O worker DEVE iniciar no startup da aplicação e consumir a fila continuamente.
- Para cada job, DEVE chamar `mem0.add(project=…, metadata)` com a atribuição por hostname.
- DEVE fazer upsert do projeto no catálogo na primeira escrita (idempotente).
- DEVE limitar a concorrência contra o LLM local (processamento controlado).
- DEVE tratar falha de extração com `mark_failed` + retentativa/log, sem perder jobs.
- A indisponibilidade do LLM NÃO DEVE travar nem perder a fila.
</requirements>

## Subtarefas
- [x] 06.1 Criar o worker assíncrono e registrá-lo no startup da aplicação.
- [x] 06.2 Consumir jobs (`dequeue`), chamar a extração/persistência via mem0 com `project` e hostname.
- [x] 06.3 Fazer upsert do projeto no catálogo.
- [x] 06.4 Aplicar limite de concorrência contra o LLM.
- [x] 06.5 Tratar falhas (retentativa/log, `mark_failed`) e marcar `mark_done` no sucesso.
- [x] 06.6 Cobrir com testes o consumo, o sucesso, a falha e a proteção de concorrência.

## Detalhes de Implementação
Não há worker existente no projeto; criar via `asyncio.create_task` no startup do `openmemory/api/main.py` (antes/junto ao `setup_mcp_server`). Reusar `AsyncMemory`/`ThreadPoolExecutor` do `mem0/memory/main.py` para o processamento e o cliente em `openmemory/api/app/utils/memory.py`. Consumir a `WriteQueue` (tarefa 05) e o upsert de catálogo (tarefa 02). Ver "Arquitetura → Fila de Escrita + Worker" e "Notas de Implementação" do ADR-004.

### Arquivos Relevantes
- `openmemory/api/main.py` — hook de startup para iniciar o worker.
- `openmemory/api/app/` (novo módulo de worker) — laço de consumo e processamento.
- `openmemory/api/app/utils/memory.py` — cliente mem0 (extração/persistência).

### Arquivos Dependentes
- `WriteQueue` (tarefa 05) — fonte dos jobs.
- Catálogo de projetos (tarefa 02) — upsert na primeira escrita.
- Núcleo mem0 com `project` (tarefa 01) — chamada de `add`.

### ADRs Relacionados
- [ADR-004: Fila interna de escrita com extração por LLM assíncrona](../adrs/adr-004.md) — Worker, concorrência e tratamento de falha.
- [ADR-002: Catálogo auto-gerenciado](../adrs/adr-002.md) — Upsert do projeto na primeira escrita.

## Entregáveis
- Worker assíncrono iniciado no startup, consumindo a fila.
- Persistência via mem0 com `project` + atribuição por hostname + upsert no catálogo.
- Limite de concorrência e tratamento de falha/retentativa.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para o fluxo fila→persistência **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Job consumido chama `mem0.add` com `project` e hostname corretos e marca `done`.
  - [ ] Falha na extração marca o job como `failed` com `error` e aplica retentativa conforme política.
  - [ ] Primeiro job de um projeto novo dispara upsert no catálogo; o segundo não duplica.
  - [ ] Limite de concorrência respeita o máximo configurado (não dispara N inferências simultâneas além do limite).
- Testes de integração:
  - [ ] Enfileirar um job → worker processa → memória fica pesquisável via `search` no projeto.
  - [ ] LLM indisponível: job não é perdido; permanece reprocessável.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Fila processada de forma assíncrona com concorrência controlada
- Falhas tratadas sem perda de jobs; catálogo atualizado na primeira escrita
