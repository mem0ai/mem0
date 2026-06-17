---
status: completed
title: Campo `project` no núcleo mem0 (add/search)
type: backend
complexity: medium
dependencies: []
---

# Campo `project` no núcleo mem0 (add/search)

## Visão Geral
Habilitar o conceito de projeto no núcleo do mem0, propagando um campo `project` da escrita para o payload do Qdrant e dos filtros para a busca. É a base de toda a segmentação por projeto e pré-requisito das tarefas de busca, worker e detecção de modelos.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O parâmetro `project` DEVE ser aceito em `add()` e propagado para o `metadata` persistido (payload do Qdrant).
- O parâmetro `project` DEVE ser aceito em `search()`/`get_all()` e aplicado como filtro de recuperação.
- O helper de filtros/metadata DEVE tratar `project` de forma análoga aos identificadores de escopo existentes, sem quebrar `user_id`/`agent_id`/`run_id`.
- A ausência de `project` NÃO DEVE quebrar o comportamento atual (retrocompatível).
- A mudança DEVE manter a coleção única (segmentação lógica por filtro), conforme ADR-003.
</requirements>

## Subtarefas
- [ ] 01.1 Estender o helper de construção de filtros/metadata para reconhecer `project`.
- [ ] 01.2 Aceitar e propagar `project` em `add()` (gravação no payload).
- [ ] 01.3 Aceitar e aplicar `project` em `search()` e `get_all()` (filtro).
- [ ] 01.4 Garantir retrocompatibilidade quando `project` não é informado.
- [ ] 01.5 Cobrir com testes unitários a propagação na escrita e o filtro na busca.

## Detalhes de Implementação
Estender o fluxo de escopo já existente em `mem0/memory/main.py`. O ponto central é o helper `_build_filters_and_metadata` (por volta da linha 272), reusado por `add()` (≈ linha 653/706) e `search()` (≈ linha 1232). Threadar `project` tanto no `base_metadata_template` (persistido) quanto no `effective_query_filters` (consulta). Ver seção "Design de Implementação → Modelos de Dados" e "Decisões-Chave" do TechSpec.

### Arquivos Relevantes
- `mem0/memory/main.py` — `_build_filters_and_metadata`, `add`, `search`, `get_all`; ponto de propagação do `project`.
- `mem0/vector_stores/qdrant.py` — payload do ponto recebe o `project` via metadata (sem mudança estrutural esperada).

### Arquivos Dependentes
- `openmemory/api/app/mcp_server.py` — passará `project` ao chamar o cliente (tarefas 03 e 07).
- `mem0/memory/main.py` (AsyncMemory) — equivalentes assíncronos devem refletir a mesma propagação.

### ADRs Relacionados
- [ADR-003: Escopo de projeto via campo `project`](../adrs/adr-003.md) — Define `project` no payload/filtros em coleção única.

## Entregáveis
- `add()`/`search()`/`get_all()` (sync e async) aceitando e propagando `project`.
- Helper de filtros/metadata tratando `project`.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para propagação escrita→payload e filtro na busca **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `add(..., project="X")` inclui `project="X"` no metadata enviado ao vector store.
  - [ ] `search(..., project="X")` adiciona `project="X"` aos filtros de consulta.
  - [ ] `get_all(..., project="X")` aplica o filtro `project`.
  - [ ] Chamada sem `project` mantém comportamento atual (nenhum filtro `project` aplicado).
  - [ ] `project` coexiste com `user_id`/`agent_id` sem conflito.
- Testes de integração:
  - [ ] Gravar com `project="A"` e buscar com `project="A"` recupera o item; buscar com `project="B"` não recupera.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- `project` é gravado no payload e filtra a busca, sem regressão no escopo existente
- Comportamento retrocompatível quando `project` é omitido
