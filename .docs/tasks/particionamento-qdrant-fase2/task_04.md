---
status: completed
title: Integrar leitura e escrita ao PartitionResolver (contrato MCP inalterado)
type: backend
complexity: medium
dependencies:
  - task_02
  - task_03
---

# Integrar leitura e escrita ao PartitionResolver (contrato MCP inalterado)

## Visão Geral
Substitui o uso da coleção fixa nos caminhos de leitura e escrita pelo `PartitionResolver`, passando `shard_key_selector` quando a busca é escopada a um projeto promovido. Mantém o filtro `{"project": ...}` e as assinaturas das ferramentas MCP intactas.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- A leitura (`search_memory`/`list_memories` no MCP e no `compat_v3`) DEVE obter a coleção ativa via `PartitionResolver`.
- A busca escopada a projeto promovido DEVE passar o `shard_key_selector` correspondente.
- A escrita (write-worker) DEVE gravar na coleção ativa resolvida, não no nome fixo.
- O filtro de projeto e as assinaturas das ferramentas MCP DEVEM permanecer inalterados.
- O caminho de cache de leitura da Fase 1 (embedding/resultado) DEVE continuar funcionando.
</requirements>

## Subtarefas
- [x] 4.1 Injetar o resolvedor na resolução de coleção do caminho de leitura (`mcp_server`, `compat_v3`).
- [x] 4.2 Passar `shard_key_selector` na busca quando o projeto for `dedicated`.
- [x] 4.3 Fazer o write-worker resolver a coleção ativa antes do `add`.
- [x] 4.4 Garantir que o cache de busca permaneça chaveado corretamente por projeto.
- [x] 4.5 Validar que nenhuma assinatura de ferramenta MCP mudou.

## Detalhes de Implementação
Ver seções "Arquitetura do Sistema" (Fluxo de dados) e "Interfaces Principais" do TechSpec. O ponto de leitura está em `mcp_server.search_memory` (montagem de `filters` e chamada a `vector_store.search`). A escrita ocorre no write-worker via `client.add`.

### Arquivos Relevantes
- `openmemory/api/app/mcp_server.py` — `search_memory`/`list_memories`; usar resolvedor + shard_key.
- `openmemory/api/app/routers/compat_v3.py` — search/add/list; mesma integração.
- `openmemory/api/app/workers/write_worker.py` — `add` na coleção ativa.

### Arquivos Dependentes
- `openmemory/api/app/utils/partitioning.py` — resolvedor consumido aqui.
- `openmemory/api/app/utils/memory.py` — cliente de memória/coleção.

### ADRs Relacionados
- [ADR-001: Particionamento lógico por projeto](adrs/adr-001.md) — busca cross-project barata preservada.
- [ADR-002: Índice de inquilino com promoção por shard key](adrs/adr-002.md) — uso do `shard_key_selector`.

## Entregáveis
- Leitura e escrita usando a coleção ativa resolvida.
- `shard_key_selector` aplicado para projetos promovidos.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de leitura/escrita por coleção resolvida **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `search_memory` chama o vector store com a coleção retornada pelo resolvedor.
  - [ ] Projeto `dedicated` resulta em busca com `shard_key_selector`; projeto `shared` sem ele.
  - [ ] Assinatura de `search_memory`/`add_memories` permanece idêntica (teste de contrato).
- Testes de integração:
  - [ ] Com `active_collection` = green, escrita e busca subsequente ocorrem na green.
  - [ ] Busca cross-project (sem projeto único) retorna resultados de múltiplos projetos.
  - [ ] Cache de busca da Fase 1 ainda gera hit/miss conforme esperado.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Toda leitura/escrita roteada pela coleção ativa, sem mudança de contrato MCP.
