---
status: completed
title: Busca por `project` e leitura direta/assíncrona (search/list)
type: backend
complexity: medium
dependencies:
  - task_01
---

# Busca por `project` e leitura direta/assíncrona (search/list)

## Visão Geral
Ajustar as ferramentas MCP de leitura (`search_memory`/`list_memories`) para filtrar por `project` e **ignorar `user_id`**, garantindo leitura compartilhada entre todas as máquinas. A leitura é direta e assíncrona contra o Qdrant, sem passar pela fila de escrita, priorizando baixa latência e concorrência.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- `search_memory` e `list_memories` DEVEM aceitar `project` e filtrar por ele.
- A busca NÃO DEVE restringir por `user_id` (leitura compartilhada na rede local).
- A leitura DEVE ser direta/assíncrona, independente da fila de escrita.
- O `top_k` DEVE ter limite padrão e o rerank DEVE ficar desativado por padrão (priorizar latência), conforme TechSpec.
- O cliente de vetor DEVE ser reutilizado (sem reconexão por chamada).
</requirements>

## Subtarefas
- [ ] 03.1 Ajustar `search_memory` para receber/filtrar por `project` e não filtrar por `user_id`.
- [ ] 03.2 Ajustar `list_memories` para escopo por `project`.
- [ ] 03.3 Garantir caminho de leitura assíncrono e cliente reutilizado.
- [ ] 03.4 Aplicar limites de `top_k` e rerank desativado por padrão.
- [ ] 03.5 Cobrir com testes o filtro por projeto e a leitura compartilhada.

## Detalhes de Implementação
Alterar `openmemory/api/app/mcp_server.py` (`search_memory` ≈ linha 150, `list_memories` ≈ linha 228), que hoje filtram por `user_id` obtido de `user_id_var`. Passar `project` ao cliente mem0 (capacidade adicionada na tarefa 01) e remover a restrição por `user_id` na recuperação. Ver seções "Caminho de Leitura" e "Decisões de leitura" do TechSpec.

### Arquivos Relevantes
- `openmemory/api/app/mcp_server.py` — `search_memory`, `list_memories`; remoção do filtro por `user_id`, inclusão de `project`.
- `openmemory/api/app/utils/memory.py` — obtenção/reuso do cliente mem0.

### Arquivos Dependentes
- `mem0/memory/main.py` — usa o `project` em filtros (tarefa 01).
- Tarefa 04 — define o hostname no slot `user_id` (não usado como filtro de leitura).

### ADRs Relacionados
- [ADR-003: Escopo de projeto via campo `project`, identidade por hostname](../adrs/adr-003.md) — Busca por `project` ignorando `user_id`.

## Entregáveis
- `search_memory`/`list_memories` filtrando por `project`, sem filtro por `user_id`.
- Leitura assíncrona com cliente reutilizado, `top_k` limitado e rerank off por padrão.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para leitura compartilhada entre hostnames **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `search_memory(query, project="A")` aplica filtro `project="A"` e não inclui `user_id` nos filtros.
  - [ ] `list_memories(project="A")` retorna apenas memórias do projeto A.
  - [ ] `top_k` padrão aplicado; rerank desativado por padrão.
- Testes de integração:
  - [ ] Memória gravada pelo hostname `maqA` no projeto `A` é recuperada em busca feita pelo hostname `maqB` no projeto `A`.
  - [ ] Busca no projeto `B` não retorna memórias do projeto `A`.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Leitura compartilhada por projeto entre máquinas distintas
- Leitura independente da fila de escrita (não bloqueia em picos de escrita)
