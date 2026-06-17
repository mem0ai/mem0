---
status: completed
title: "`add_memories` enfileira + ack imediato"
type: backend
complexity: medium
dependencies:
  - task_04
  - task_05
---

# `add_memories` enfileira + ack imediato

## Visão Geral
Transformar a ferramenta MCP `add_memories` em uma operação não bloqueante: validar a entrada, enfileirar o job de escrita e retornar um ack imediato com `job_id`, sem aguardar a extração por LLM. Isso entrega a meta de escrita não bloqueante do PRD.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- `add_memories` DEVE aceitar `text` e `project` e enfileirar o job em vez de extrair de forma síncrona.
- DEVE retornar um ack imediato no formato `{ "status": "queued", "job_id": ... }`.
- DEVE incluir no job o hostname (atribuição) e o `client_name` de origem.
- A entrada inválida (ex.: `project` ausente) DEVE retornar erro descritivo sem enfileirar.
- NÃO DEVE chamar a extração por LLM no caminho da requisição.
</requirements>

## Subtarefas
- [ ] 07.1 Ajustar a assinatura de `add_memories` para `text` + `project`.
- [ ] 07.2 Validar a entrada e enfileirar via `WriteQueue` com hostname e `client_name`.
- [ ] 07.3 Retornar ack imediato com `job_id`.
- [ ] 07.4 Tratar entrada inválida com erro claro (sem enfileirar).
- [ ] 07.5 Cobrir com testes o enfileiramento, o ack e a validação.

## Detalhes de Implementação
Modificar `openmemory/api/app/mcp_server.py` (`add_memories` ≈ linha 65), que hoje chama `memory_client.add(...)` de forma síncrona. Passar a usar `WriteQueue.enqueue` (tarefa 05) com o hostname capturado (tarefa 04) e o `client_name` da context var. Ver "Design de Implementação → Interfaces Principais" e "Endpoints de API" do TechSpec.

### Arquivos Relevantes
- `openmemory/api/app/mcp_server.py` — `add_memories`; troca de extração síncrona por enfileiramento.

### Arquivos Dependentes
- `WriteQueue` (tarefa 05) — destino do enqueue.
- Worker (tarefa 06) — processa o job enfileirado.
- Identidade por hostname (tarefa 04) — atribuição no job.

### ADRs Relacionados
- [ADR-004: Fila interna de escrita com extração por LLM assíncrona](../adrs/adr-004.md) — Ack imediato + enfileiramento.

## Entregáveis
- `add_memories(text, project)` enfileirando e retornando ack com `job_id`.
- Validação de entrada com erro descritivo.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para enfileiramento ponta a ponta **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `add_memories("texto", project="A")` enfileira um job e retorna `{status: "queued", job_id}`.
  - [ ] O job enfileirado contém hostname e `client_name` corretos.
  - [ ] `project` ausente retorna erro descritivo e não enfileira.
  - [ ] A extração por LLM não é chamada no caminho da requisição (mock não invocado).
- Testes de integração:
  - [ ] Chamada `add_memories` cria item na `write_queue` consumível pelo worker.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Escrita não bloqueante com ack imediato
- Entrada inválida tratada sem enfileirar
