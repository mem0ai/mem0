---
status: completed
title: Visibilidade operacional - tamanhos por projeto + métricas e alertas
type: backend
complexity: medium
dependencies:
  - task_01
---

# Visibilidade operacional - tamanhos por projeto + métricas e alertas

## Visão Geral
Dá ao operador visibilidade e antecipação: endpoint que lista o tamanho/saúde por projeto (incluindo proximidade do limiar) e métricas Prometheus com alertas de tamanho de projeto e progresso de migração. É o que permite promover um projeto antes de a busca degradar.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir `GET /admin/projects/sizes` retornando, por projeto, `memory_count`, `partition_tier`, `shard_key` e uma flag de proximidade do limiar.
- DEVEM ser expostas métricas de `qdrant_collection_size` por projeto e `project_size_over_threshold`.
- DEVE ser exposta a métrica de progresso de migração (`migration_copy_progress`).
- As métricas DEVEM seguir o padrão de definição centralizado em `utils/metrics.py`.
- O endpoint DEVE refletir o catálogo `projects` sem recalcular contagens de forma cara no caminho de requisição.
</requirements>

## Subtarefas
- [x] 9.1 Implementar `GET /admin/projects/sizes` lendo `projects` (count/tier/shard_key + flag de limiar).
- [x] 9.2 Definir as métricas de tamanho por projeto e de limiar excedido em `metrics.py`.
- [x] 9.3 Expor a métrica de progresso de migração (`migration_points_copied_total`).
- [x] 9.4 Documentar os limites de alerta (tamanho de projeto, progresso parado).
- [x] 9.5 Registrar o endpoint no router administrativo.

## Detalhes de Implementação
Ver seção "Monitoramento e Observabilidade" do TechSpec. Reutilizar `utils/metrics.py` (padrão `prometheus_client` em nível de módulo) e expor via o endpoint de métricas existente (`routers/ops_metrics.py`). O endpoint de tamanhos vive no router administrativo (criado na tarefa 07).

### Arquivos Relevantes
- `openmemory/api/app/utils/metrics.py` — definir contadores/gauges novos.
- `openmemory/api/app/routers/admin.py` — endpoint `/admin/projects/sizes`.
- `openmemory/api/app/routers/ops_metrics.py` — exposição Prometheus existente.
- `openmemory/api/app/models.py` — `Project` (`memory_count`/tier/shard_key).

### Arquivos Dependentes
- `openmemory/api/main.py` — registro do router (se ainda não registrado pela tarefa 07).

### ADRs Relacionados
- [ADR-002: Índice de inquilino com promoção por shard key dedicado](adrs/adr-002.md) — limiar de promoção observado por estas métricas.

## Entregáveis
- Endpoint `GET /admin/projects/sizes` com proximidade de limiar.
- Métricas de tamanho por projeto, limiar excedido e progresso de migração.
- Limites de alerta documentados.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração do endpoint de tamanhos **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `project_size_over_threshold` sinaliza quando `memory_count` excede o limiar configurado.
  - [ ] A resposta de `/sizes` inclui `partition_tier` e `shard_key` por projeto.
  - [ ] Métricas são registradas no formato `prometheus_client` esperado.
- Testes de integração:
  - [ ] `GET /admin/projects/sizes` retorna 200 com a lista de projetos e a flag de limiar correta.
  - [ ] A métrica de progresso de migração reflete o `scroll_cursor`/status corrente.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Operador enxerga tamanho/saúde por projeto e é alertado antes da degradação.
