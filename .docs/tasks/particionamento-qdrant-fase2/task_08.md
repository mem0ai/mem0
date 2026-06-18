---
status: completed
title: Promoção de projeto gigante a shard_key dedicado
type: backend
complexity: high
dependencies:
  - task_02
  - task_06
  - task_07
---

# Promoção de projeto gigante a shard_key dedicado

## Visão Geral
Implementa a rota de escala para projetos que cruzam o limiar de tamanho: atribuir um `shard_key` dedicado, mover os pontos do projeto para esse shard e marcar o projeto como `dedicated`, sem mudar o contrato de busca. A busca escopada ao projeto promovido passa a usar `shard_key_selector`.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- A promoção DEVE criar o `shard_key` dedicado e reescrever os pontos do projeto nesse shard, preservando IDs e payload.
- A promoção DEVE atualizar `projects.partition_tier=dedicated` e `projects.shard_key`, invalidando o cache do resolvedor.
- A reescrita DEVE ser idempotente e retomável (reaproveitar o mecanismo de cópia/checkpoint do worker de migração).
- O endpoint `POST /admin/projects/{name}/promote` DEVE enfileirar a promoção sem bloquear a requisição.
- A busca escopada ao projeto promovido DEVE usar `shard_key_selector`; a busca cross-project DEVE continuar correta.
- O limiar de promoção DEVE ser parametrizável (não fixo em código).
</requirements>

## Subtarefas
- [x] 8.1 Implementar a atribuição de `shard_key` dedicado para um projeto.
- [x] 8.2 Reescrever os pontos do projeto no shard dedicado de forma idempotente/retomável.
- [x] 8.3 Atualizar `partition_tier`/`shard_key` em `projects` e invalidar o resolvedor.
- [x] 8.4 Expor `POST /admin/projects/{name}/promote` (enfileira a promoção).
- [x] 8.5 Parametrizar o limiar de promoção (`PROJECT_PROMOTION_THRESHOLD`, task_09).

## Detalhes de Implementação
Ver seções "Decisões-Chave" e "Endpoints de API" do TechSpec, e o mecanismo de custom sharding da tarefa 02. A reescrita reaproveita a cópia com checkpoint do worker de migração (tarefa 06). O roteamento por `shard_key` na busca vem da tarefa 04.

### Arquivos Relevantes
- `openmemory/api/app/workers/migration_worker.py` — estende a lógica de cópia para a promoção.
- `mem0/vector_stores/qdrant.py` — criação/atribuição de shard key e `shard_key_selector`.
- `openmemory/api/app/routers/admin.py` — endpoint de promoção.
- `openmemory/api/app/models.py` — atualização de `Project` (tier/shard_key).

### Arquivos Dependentes
- `openmemory/api/app/utils/partitioning.py` — `route_for` passa a retornar o shard_key.
- `openmemory/api/app/mcp_server.py` — busca escopada usa o `shard_key_selector`.

### ADRs Relacionados
- [ADR-002: Índice de inquilino com promoção por shard key dedicado](adrs/adr-002.md) — define a promoção sob demanda.
- [ADR-001: Particionamento lógico por projeto](adrs/adr-001.md) — promoção não pode quebrar a busca cross-project.

## Entregáveis
- Promoção de projeto a `shard_key` dedicado (atribuição + reescrita idempotente).
- Endpoint `POST /admin/projects/{name}/promote`.
- Limiar de promoção parametrizável.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração da promoção ponta a ponta **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Promoção marca `partition_tier=dedicated` e grava `shard_key`, chamando `invalidate()`.
  - [ ] Reexecutar a promoção do mesmo projeto não duplica pontos (idempotência).
  - [ ] `POST /promote` retorna aceitação (enfileirado) sem executar a reescrita de forma síncrona.
- Testes de integração:
  - [ ] Após promover, os pontos do projeto residem no shard dedicado e a busca escopada usa `shard_key_selector` retornando o conjunto correto.
  - [ ] Busca cross-project continua retornando o projeto promovido junto aos demais.
  - [ ] Limiar configurado diferente altera quando a promoção é sinalizada.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Projeto gigante isolado em shard dedicado sem mudança de contrato de busca nem regressão cross-project.
