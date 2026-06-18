---
status: completed
title: Extensão do provider Qdrant - índice de inquilino + índices de payload + criação com shard/replicação
type: backend
complexity: high
dependencies: []
---

# Extensão do provider Qdrant - índice de inquilino + índices de payload + criação com shard/replicação

## Visão Geral
Estende o provider `Qdrant` para indexar `project` como chave de inquilino (`is_tenant=true`), criar os índices de payload adicionais (`type`, `created_at`, `hash`) e permitir criar a coleção com `shard_number`/`replication_factor` e sharding customizado. É o que torna o filtro de projeto rápido em escala e habilita a promoção de gigantes.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O campo `project` DEVE ser indexado como `keyword` com `is_tenant=true` em Qdrant remoto.
- DEVEM ser criados índices de payload para `type` (keyword), `created_at` (datetime) e `hash` (keyword), além dos existentes (`user_id`, `agent_id`, `run_id`, `actor_id`).
- A criação de coleção DEVE aceitar `shard_number` e `replication_factor` parametrizáveis e suportar `sharding_method=CUSTOM`.
- `search`/`search_batch` DEVEM aceitar opcionalmente um `shard_key_selector` para buscas escopadas a projeto promovido.
- O caminho local/single-node DEVE permanecer funcional (sem criar índices não suportados), preservando o comportamento atual.
- A busca cross-project (sem filtro de projeto) DEVE continuar correta após a indexação.
</requirements>

## Subtarefas
- [x] 2.1 Estender `_create_filter_indexes` para incluir `project` (inquilino) e os campos `type`/`created_at`/`hash`.
- [x] 2.2 Parametrizar `create_col` para `shard_number`/`replication_factor` e habilitar `sharding_method=CUSTOM`.
- [x] 2.3 Adicionar suporte a `shard_key_selector` opcional em `search` e `search_batch`.
- [x] 2.4 Expor helpers para criar/atribuir shard key (consumidos pela promoção, tarefa 08).
- [x] 2.5 Garantir no-op seguro de índices/sharding no modo local.

## Detalhes de Implementação
Ver seções "Interfaces Principais" e "Decisões-Chave" do TechSpec. Usar `models.KeywordIndexParams(type="keyword", is_tenant=True)` para o inquilino. Não alterar o formato do payload — apenas a indexação e a criação da coleção.

### Arquivos Relevantes
- `mem0/vector_stores/qdrant.py` — `_create_filter_indexes`, `create_col`, `search`, `search_batch`; ponto central da tarefa.
- `mem0/configs/vector_stores/qdrant.py` — config do provider; expor novos parâmetros (shard/replicação) se necessário.

### Arquivos Dependentes
- `openmemory/api/app/utils/memory.py` — `get_default_memory_config`; passa os parâmetros de criação da coleção.
- `mem0/vector_stores/base.py` — assinatura base de `search` se for alterada.

### ADRs Relacionados
- [ADR-002: Índice de inquilino com promoção por shard key dedicado e cluster 3 nós](adrs/adr-002.md) — define exatamente esta extensão.
- [ADR-001: Particionamento lógico por projeto](adrs/adr-001.md) — justifica a indexação de inquilino na coleção compartilhada.

## Entregáveis
- `project` indexado como inquilino + índices `type`/`created_at`/`hash`.
- `create_col` parametrizável (shard/replicação/custom sharding).
- `shard_key_selector` opcional em busca.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração contra Qdrant de teste **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `_create_filter_indexes` chama `create_payload_index` para `project` com `is_tenant=True` em modo remoto.
  - [ ] `_create_filter_indexes` cria índices para `type`/`created_at`/`hash` com os schemas corretos.
  - [ ] Modo local não tenta criar índices (no-op) e não levanta exceção.
  - [ ] `search` sem `shard_key_selector` mantém o comportamento atual (filtro de projeto).
- Testes de integração:
  - [ ] Criar coleção com `shard_number`/`replication_factor` e confirmar a config retornada por `get_collection`.
  - [ ] Inserir pontos de 2 projetos e buscar com filtro de projeto retorna só o projeto certo; busca sem filtro retorna ambos (cross-project).
  - [ ] Busca com `shard_key_selector` em projeto com shard dedicado retorna os pontos esperados.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Coleção nova nasce com inquilino + índices + shard/replicação configuráveis.
- Sem regressão de busca por projeto nem cross-project.
