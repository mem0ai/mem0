---
status: completed
title: PartitionResolver - resolução da coleção ativa e shard_key por projeto
type: backend
complexity: medium
dependencies:
  - task_01
---

# PartitionResolver - resolução da coleção ativa e shard_key por projeto

## Visão Geral
Cria o `PartitionResolver`, ponto único que resolve qual coleção está ativa (blue ou green) e qual `shard_key` usar para um projeto, lendo o estado de `migration_state`/`projects` com cache em memória invalidável. Substitui o `collection_name` fixo `"openmemory"` por roteamento dinâmico, sem alterar o contrato MCP.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE expor `route_for(project)` retornando coleção ativa e `shard_key` (definido só para projeto com `partition_tier=dedicated`).
- DEVE expor `active_collection()` e `invalidate()` (este chamado no flip e na promoção).
- DEVE manter cache em memória do estado e invalidá-lo de forma explícita, sem reler o banco a cada chamada.
- DEVE degradar para a coleção configurada por env quando não houver linha em `migration_state` (compatível com pré-migração).
- NÃO DEVE alterar a assinatura das ferramentas MCP (`search_memory`, `add_memories`).
</requirements>

## Subtarefas
- [x] 3.1 Definir as estruturas de rota (coleção + shard_key opcional) conforme a seção "Interfaces Principais" do TechSpec.
- [x] 3.2 Implementar leitura de `migration_state.active_collection` e de `projects.partition_tier`/`shard_key`.
- [x] 3.3 Implementar cache em memória com `invalidate()`.
- [x] 3.4 Implementar fallback para a coleção de env quando o estado estiver ausente.
- [x] 3.5 Expor o resolvedor como dependência reutilizável por API e workers.

## Detalhes de Implementação
Ver seção "Interfaces Principais" do TechSpec (tipo `PartitionResolver`/`CollectionRoute`). Novo módulo em `openmemory/api/app/utils/`. Não reproduzir o código do TechSpec — implementar a interface descrita lá.

### Arquivos Relevantes
- `openmemory/api/app/utils/partitioning.py` — novo módulo do resolvedor.
- `openmemory/api/app/models.py` — `migration_state` e `Project` (consumidos pela leitura de estado).
- `openmemory/api/app/utils/memory.py` — `get_default_memory_config` (origem do fallback por env).

### Arquivos Dependentes
- `openmemory/api/app/mcp_server.py` — consumirá o resolvedor (tarefa 04).
- `openmemory/api/app/workers/write_worker.py` — consumirá o resolvedor (tarefas 04/05).

### ADRs Relacionados
- [ADR-003: Migração blue-green com worker dedicado e estado no PostgreSQL](adrs/adr-003.md) — define a coleção ativa resolvida via estado.

## Entregáveis
- Módulo `partitioning.py` com `PartitionResolver` (route_for/active_collection/invalidate).
- Cache em memória com invalidação explícita e fallback por env.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de leitura de estado do banco **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `route_for` de projeto `shared` retorna a coleção ativa e `shard_key=None`.
  - [ ] `route_for` de projeto `dedicated` retorna o `shard_key` registrado.
  - [ ] `invalidate()` força releitura na chamada seguinte (estado alterado é refletido).
  - [ ] Sem linha em `migration_state`, retorna a coleção da env (fallback).
- Testes de integração:
  - [ ] Após atualizar `active_collection` no banco e chamar `invalidate()`, `active_collection()` retorna o novo valor.
  - [ ] Promover um projeto (tier=dedicated + shard_key) reflete em `route_for` após invalidação.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Roteamento de coleção/shard centralizado e estável sob cache.
- Contrato MCP inalterado.
