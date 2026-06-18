---
status: pending
title: Observabilidade e medição de qualidade
type: backend
complexity: medium
dependencies:
  - task_03
  - task_06
  - task_10
---

# Observabilidade e medição de qualidade

## Visão Geral
Fecha o ciclo da métrica-chave do PRD: instrumenta os contadores/gauges de governança, calcula a métrica-proxy contínua de qualidade (quase-duplicatas no top-K) no caminho de busca e roda uma avaliação periódica com LLM-juiz, expondo um índice de qualidade via endpoint. Também emite o alerta de taxa de reversão que pausa o Incremento 2.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVEM existir os contadores/gauges da seção "Monitoramento e Observabilidade" do TechSpec (dedup/poda/merge/contradição/purge/revert, profundidade/erros/latência de job, `governance_revert_rate`).
- A métrica-proxy `retrieval_duplicate_in_topk_ratio` DEVE ser amostrada a partir de buscas reais, sem impacto perceptível de latência.
- O LLM-juiz periódico DEVE amostrar resultados e produzir `retrieval_quality_index`, agendado pelo mesmo mecanismo de jobs.
- O endpoint `GET /admin/governance/quality` DEVE retornar o último índice (proxy + LLM-juiz).
- As métricas DEVEM ser expostas pelo endpoint `/metrics` existente (registry Prometheus).
- `governance_revert_rate` acima de limiar DEVE ser observável para servir de gatilho de pausa do Incremento 2.
</requirements>

## Subtarefas
- [ ] 12.1 Adicionar os contadores/gauges de governança ao módulo de métricas.
- [ ] 12.2 Instrumentar a métrica-proxy de quase-duplicatas no top-K no caminho de busca (amostragem).
- [ ] 12.3 Implementar o job de LLM-juiz periódico que calcula `retrieval_quality_index`.
- [ ] 12.4 Expor `GET /admin/governance/quality` com proxy + índice do LLM-juiz.
- [ ] 12.5 Garantir exposição via `/metrics` e o gauge de `governance_revert_rate`.

## Detalhes de Implementação
Ver seção "Monitoramento e Observabilidade" do TechSpec. Estender `utils/metrics.py` (padrão Prometheus existente) e expor via `routers/ops_metrics.py`. O LLM-juiz é um job agendado (mecanismo da task_06) que reusa o cliente LLM; a proxy amostra no caminho de busca (task_03). Endpoint segue o padrão de `admin.py` (task_11).

### Arquivos Relevantes
- `openmemory/api/app/utils/metrics.py` — adicionar métricas de governança.
- `openmemory/api/app/governance/quality_eval.py` — **novo**: job LLM-juiz + cálculo do índice.
- `openmemory/api/app/routers/ops_metrics.py` — exposição `/metrics`.
- `openmemory/api/app/routers/admin.py` — endpoint `/admin/governance/quality`.
- `openmemory/api/app/mcp_server.py` — ponto de amostragem da proxy na busca.

### Arquivos Dependentes
- `openmemory/api/app/workers/governance_worker.py` — agenda/execução do LLM-juiz (tasks 05/06).
- `openmemory/api/app/governance/consolidation.py` — emite `governance_revert_rate`/merge counters (task_10).

### ADRs Relacionados
- [ADR-004: Consolidação semântica por candidatura via vetor + adjudicação por LLM](adrs/adr-004.md) — taxa de reversão como gatilho de pausa.
- [ADR-001: Governança automática com rede de segurança, faseada](adrs/adr-001.md) — qualidade da recuperação como métrica-chave.

## Entregáveis
- Métricas de governança + proxy de qualidade + `governance_revert_rate`.
- Job LLM-juiz periódico e endpoint `/admin/governance/quality`.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de exposição de métricas e do índice de qualidade **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Cada ação de governança incrementa o contador correspondente (dedup/poda/merge/contradição/purge/revert).
  - [ ] `retrieval_duplicate_in_topk_ratio` é calculado corretamente a partir de um resultado de busca com quase-duplicatas conhecidas.
  - [ ] LLM-juiz (mockado) produz `retrieval_quality_index` a partir de uma amostra.
  - [ ] `governance_revert_rate` reflete reversões/ações no período.
- Testes de integração:
  - [ ] `/metrics` expõe as novas métricas no formato Prometheus.
  - [ ] `GET /admin/governance/quality` retorna proxy + índice do LLM-juiz.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Qualidade da recuperação observável (proxy contínuo + LLM-juiz periódico)
- Taxa de reversão disponível como gatilho de pausa do Incremento 2
