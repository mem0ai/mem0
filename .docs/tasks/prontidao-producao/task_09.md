---
status: pending
title: Regras de alerta Prometheus (+ Alertmanager opcional)
type: infra
complexity: medium
dependencies:
  - task_06
  - task_07
  - task_08
---

# Tarefa 9: Regras de alerta Prometheus (+ Alertmanager opcional)

## Visão Geral
Transforma as métricas existentes e as novas (quota, cold tier, backup) em alertas acionáveis, para que a operação seja avisada antes do impacto ao usuário. Inclui Alertmanager opcional para roteamento.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVEM existir regras de alerta Prometheus versionadas para: latência p99 de busca > 500ms; crescimento sustentado de `write_queue_depth`; `governance_job_errors_total` > 0 em janela; `backup_age_seconds` > 24h (RPO violado); `project_size_over_threshold` > 0.
- As regras DEVEM referenciar métricas que existem (incluindo as criadas nas tasks 02/06/07).
- Alertmanager DEVE ser opcional e, se presente, rotear os alertas.
- As regras DEVEM ser validáveis (ex.: `promtool check rules`).
</requirements>

## Subtarefas
- [ ] 9.1 Escrever o arquivo de regras de alerta cobrindo os limiares definidos.
- [ ] 9.2 Conectar o Prometheus às regras no compose de observabilidade.
- [ ] 9.3 Adicionar Alertmanager opcional e roteamento básico.
- [ ] 9.4 Validar as regras com `promtool`.

## Detalhes de Implementação
Ver ADR-004 e seção "Monitoramento e Observabilidade" do TechSpec. As métricas-fonte estão em `app/utils/metrics.py` e nas tasks 02/06/07. Limiares iniciais documentados no TechSpec.

### Arquivos Relevantes
- `openmemory/compose/observability.yml` — Prometheus/Alertmanager.
- `openmemory/api/app/utils/metrics.py` — métricas-fonte dos alertas.

### Arquivos Dependentes
- `openmemory/observability/alerts.yml` (novo) — regras de alerta.

### ADRs Relacionados
- [ADR-004: Observabilidade — tracing distribuído com OpenTelemetry e alertas Prometheus](adrs/adr-004.md) — define alertas.

## Entregáveis
- Arquivo de regras de alerta carregado pelo Prometheus.
- Alertmanager opcional configurado.
- Validação das regras com `promtool` **(OBRIGATÓRIO como teste)**
- Teste de integração: alerta dispara quando a condição é simulada **(OBRIGATÓRIO)**

## Testes
- Testes unitários (validação estática):
  - [ ] `promtool check rules` passa sem erros.
  - [ ] Cada alerta referencia uma métrica existente.
- Testes de integração:
  - [ ] Simular `backup_age_seconds > 24h` coloca o alerta em estado firing.
  - [ ] Simular erro de job de governança dispara o alerta correspondente.
- Meta de cobertura: >= 80% (das regras definidas, exercitadas)
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Regras válidas e carregadas
- Alertas disparam antes do impacto percebido em cenários simulados
