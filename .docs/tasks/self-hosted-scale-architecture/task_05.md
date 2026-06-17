---
status: pending
title: Cache Redis de embedding e resultado de busca com invalidação por escrita
type: backend
complexity: high
dependencies:
  - task_03
  - task_04
---

# Cache Redis de embedding e resultado de busca com invalidação por escrita

## Visão Geral
Introduz um cache Redis em duas camadas no caminho de leitura — vetor de embedding e resultado de busca — com invalidação por `project` na escrita. Como a inferência usa Ollama/llama.cpp sem batching contínuo, o cache é a principal alavanca para atingir a latência sub-segundo.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE cachear o vetor de embedding por hash da query normalizada (TTL configurável 1–24h).
- DEVE cachear o resultado de busca por `(project, query, top_k, filter_hash)` (TTL curto ~5min).
- A normalização da query DEVE ser idêntica entre as duas camadas (trim, lowercase, collapse whitespace).
- A escrita de um `project` DEVE invalidar o cache de resultado de busca daquele `project` após o upsert no Qdrant.
- O cache DEVE degradar graciosamente: indisponibilidade do Redis resulta em miss (caminho normal), nunca em exceção que bloqueie a leitura.
</requirements>

## Subtarefas
- [ ] 5.1 Criar a camada de cache (módulo dedicado) com as operações de embedding e resultado.
- [ ] 5.2 Centralizar a normalização de query reutilizada pelas duas camadas.
- [ ] 5.3 Integrar o cache no fluxo de `search_memory` (embedding e resultado).
- [ ] 5.4 Acionar a invalidação por `project` no worker após o upsert.
- [ ] 5.5 Garantir degradação graciosa quando o Redis estiver indisponível.

## Detalhes de Implementação
Ver seções "Interfaces Principais" (interface `ReadCache`), "Modelos de Dados" (chaves de cache) e "Fluxos" do TechSpec. O cache nunca deve bloquear a leitura; a invalidação ocorre no ponto único pós-upsert no worker.

### Arquivos Relevantes
- `openmemory/api/app/utils/read_cache.py` — novo módulo do cache de leitura.
- `openmemory/api/app/mcp_server.py` — integrar cache de embedding e resultado em `search_memory`.
- `openmemory/api/app/workers/write_worker.py` — chamar invalidação por `project` após upsert.

### Arquivos Dependentes
- `openmemory/docker-compose.yml` — base para o serviço Redis no stack.

### ADRs Relacionados
- [ADR-005: Cache Redis de embedding e de resultado de busca com invalidação por escrita](../adrs/adr-005.md) — Define as duas camadas, chaves, TTLs e invalidação.
- [ADR-002: Embedding e LLM dedicados (Ollama/llama.cpp)](../adrs/adr-002.md) — Justifica o cache como alavanca principal de latência.

## Entregáveis
- Módulo de cache de leitura (embedding + resultado).
- Integração no `search_memory` e invalidação no worker.
- Serviço Redis no stack.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração do fluxo de leitura com cache **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Embedding: miss grava no cache; hit subsequente retorna o vetor sem chamar a inferência.
  - [ ] Resultado: hit por `(project, query, top_k, filter_hash)` retorna sem consultar o Qdrant.
  - [ ] Normalização: queries equivalentes (espaços/caixa) geram a mesma chave.
  - [ ] Redis indisponível → operação retorna miss sem lançar exceção.
- Testes de integração:
  - [ ] Cache frio (miss → inferência → Qdrant) seguido de cache quente (hit) no `search_memory`.
  - [ ] Escrita em um `project` invalida o cache de busca daquele `project` (resultado seguinte recalculado).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Latência de leitura cai significativamente em cache quente.
- Resultados não ficam stale além do TTL após escrita (invalidação efetiva).
