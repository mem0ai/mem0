---
status: pending
title: Índice de payload state no Qdrant + filtro state=active na busca
type: backend
complexity: high
dependencies:
  - task_01
---

# Índice de payload state no Qdrant + filtro state=active na busca

## Visão Geral
Garante que memórias em quarentena (ou deletadas) nunca apareçam na busca, sem alterar o contrato MCP. Adiciona o índice de payload `state` no Qdrant e injeta um filtro implícito `state="active"` num ponto único do caminho de leitura. É entregue cedo para assegurar não-regressão antes de qualquer ação destrutiva.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O campo `state` DEVE ser indexado como keyword no payload do Qdrant (na criação de coleção e via backfill na base existente).
- Toda busca DEVE excluir resultados cujo `state` não seja `active`, sem mudar a assinatura das ferramentas MCP (`search_memory`) nem dos endpoints `compat_v3`.
- O filtro `state="active"` DEVE ser aplicado num ponto único de montagem de filtros (evitar duplicação espalhada).
- Pontos sem `state` no payload (legados) DEVEM ser tratados como `active` (não sumir da busca).
- Busca por projeto e cross-project DEVEM continuar retornando o mesmo conjunto `active` de antes.
</requirements>

## Subtarefas
- [ ] 3.1 Adicionar `state` como índice de payload keyword na criação de coleção do provider.
- [ ] 3.2 Prover backfill do índice/atributo `state` para coleções existentes (default `active`).
- [ ] 3.3 Injetar `state="active"` na montagem do filtro de busca (ponto único).
- [ ] 3.4 Garantir que o contrato MCP/compat_v3 permanece inalterado externamente.
- [ ] 3.5 Cobrir regressão de busca por projeto e cross-project.

## Detalhes de Implementação
Ver seções "Arquitetura do Sistema" e "Análise de Impacto" do TechSpec e o [ADR-003](adrs/adr-003.md). O filtro é montado em `_create_filter` (qdrant.py, ~linha 385) e os filtros do caminho MCP em `mcp_server.py`/`compat_v3.py`/`utils/memory.py`. Tratar pontos sem `state` exige cuidado (não filtrar legados para fora).

### Arquivos Relevantes
- `mem0/vector_stores/qdrant.py` — `_create_filter` (~385), `search` (~461), criação de coleção/índices.
- `openmemory/api/app/mcp_server.py` — montagem de `filters = {"project": ...}` (linhas ~192/221/276/282).
- `openmemory/api/app/routers/compat_v3.py` — `_walk_clauses`/`_extract_scope` (linhas ~47/61).
- `openmemory/api/app/utils/memory.py` — construção do cliente/escopo de busca.

### Arquivos Dependentes
- `openmemory/api/app/utils/quarantine.py` — depende deste filtro para "esconder" quarentenadas (task_04).
- `tests/vector_stores/test_qdrant.py` — testes de filtro a estender.
- `openmemory/api/tests/test_mcp_read_project.py` — regressão de leitura por projeto.

### ADRs Relacionados
- [ADR-003: Estado `quarantined` dedicado com retenção do vetor e expurgo diferido](adrs/adr-003.md) — exige excluir quarentenadas por filtro, mantendo o vetor.

## Entregáveis
- Índice de payload `state` + backfill para coleções existentes.
- Filtro implícito `state="active"` num ponto único da busca.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de busca com memórias quarentenadas/legadas **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `_create_filter` inclui `state="active"` mesmo quando só há filtro de projeto.
  - [ ] Filtro combina corretamente `project` + `state` + filtros existentes (user/agent/type).
  - [ ] Busca cross-project (sem filtro de projeto) ainda aplica `state="active"`.
- Testes de integração:
  - [ ] Memória `quarantined` não retorna na busca; memória `active` retorna.
  - [ ] Ponto legado sem `state` no payload é tratado como `active` e retorna.
  - [ ] Conjunto de resultados por projeto é idêntico ao da Fase 2 quando não há quarentena.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Contrato MCP/compat_v3 inalterado externamente
- Nenhuma memória `active` ou legada deixa de aparecer por causa do filtro
