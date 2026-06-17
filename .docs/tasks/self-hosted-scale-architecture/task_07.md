---
status: pending
title: Observabilidade (/health, /metrics, Prometheus/Grafana)
type: backend
complexity: medium
dependencies:
  - task_03
  - task_05
  - task_06
---

# Observabilidade (/health, /metrics, Prometheus/Grafana)

## Visão Geral
Adiciona visibilidade operacional inexistente hoje: endpoints `/health` e `/metrics`, instrumentação dos caminhos de leitura e escrita, e um painel Grafana com as metas do PRD. Sem isso não é possível provar a métrica de sucesso de latência p99 nem detectar degradação.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE expor `/health` com checagens de DB, Qdrant, cliente mem0 e profundidade de fila, retornando status degradado adequado quando algum componente falhar.
- DEVE expor `/metrics` em formato Prometheus com latência p99 de busca, profundidade/lag de fila, hit rate de cache (embedding e busca) e taxa de erro de worker.
- Logs DEVEM ser estruturados com `request_id`/`job_id` para correlação entre leitura e escrita.
- DEVE existir um painel Grafana refletindo as metas do PRD (p99, lag, hit rate) e os limites de alerta do TechSpec.
- A instrumentação NÃO DEVE alterar o contrato MCP nem degradar perceptivelmente a latência.
</requirements>

## Subtarefas
- [ ] 7.1 Implementar o endpoint `/health` com as checagens de dependências e profundidade de fila.
- [ ] 7.2 Implementar `/metrics` (Prometheus) com as métricas-chave do TechSpec.
- [ ] 7.3 Instrumentar os caminhos de leitura (latência/cache) e escrita (lag/erro).
- [ ] 7.4 Adotar logs estruturados com `request_id`/`job_id`.
- [ ] 7.5 Definir Prometheus/Grafana no stack e o painel com as metas/alertas.

## Detalhes de Implementação
Ver seção "Monitoramento e Observabilidade" do TechSpec (tabela de métricas e alertas). O `/health` é consumido pelo reverse proxy/Swarm; as métricas instrumentam os caminhos entregues nas tarefas 3, 5 e 6.

### Arquivos Relevantes
- `openmemory/api/app/routers/` — novo router de `/health` e `/metrics`.
- `openmemory/api/app/mcp_server.py` — instrumentar latência de busca e cache.
- `openmemory/api/app/workers/write_worker.py` — instrumentar lag/erro de processamento.

### Arquivos Dependentes
- `openmemory/api/main.py` — registrar o novo router.
- `openmemory/docker-compose.yml` — base para Prometheus/Grafana no stack.

### ADRs Relacionados
- (Decisão de observabilidade registrada na seção "Considerações Técnicas" do TechSpec; sem ADR dedicado.)

## Entregáveis
- Endpoints `/health` e `/metrics`.
- Instrumentação de leitura/escrita + logs estruturados.
- Painel Grafana com metas e alertas.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração dos endpoints operacionais **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `/health` retorna 200 com todas as dependências saudáveis.
  - [ ] `/health` retorna 503 quando uma dependência (ex.: DB ou Qdrant) está indisponível.
  - [ ] `/metrics` expõe as séries esperadas (latência, fila, cache hit, erro) em formato Prometheus.
- Testes de integração:
  - [ ] Uma busca incrementa as métricas de latência e de cache hit/miss correspondentes.
  - [ ] Um job processado atualiza profundidade/lag de fila e contador de sucesso/erro.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Métricas de p99, lag e hit rate visíveis no Grafana com alertas configurados.
- `/health` utilizável pelo proxy/Swarm para readiness.
