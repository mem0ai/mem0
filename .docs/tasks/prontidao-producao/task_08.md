---
status: pending
title: Instrumentação OpenTelemetry + Collector + backend de traces
type: infra
complexity: high
dependencies:
  - task_01
---

# Tarefa 8: Instrumentação OpenTelemetry + Collector + backend de traces

## Visão Geral
Habilita diagnóstico ponta a ponta: instrumenta a API FastAPI e os workers com OpenTelemetry (spans em embed → Qdrant → LLM → fila) e exporta via OTLP para um Collector e um backend de traces (Tempo/Jaeger), correlacionando com `request_id`/`job_id` já existentes.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- A API e os workers DEVEM ser instrumentados com OpenTelemetry (auto-instrumentação FastAPI/HTTPX/SQLAlchemy + spans manuais nos trechos críticos).
- Os spans DEVEM correlacionar com `request_id` (middleware) e `job_id` (logging_context).
- A exportação DEVE ser OTLP para um Collector; falha de export NÃO PODE quebrar a requisição.
- DEVE haver um backend de traces (Tempo ou Jaeger) no compose de observabilidade.
- O sampling DEVE ser configurável por env.
</requirements>

## Subtarefas
- [ ] 8.1 Adicionar dependências OTel e inicializar o tracer na API e nos workers.
- [ ] 8.2 Aplicar auto-instrumentação (FastAPI/HTTPX/SQLAlchemy).
- [ ] 8.3 Criar spans manuais para embed, busca Qdrant, extração LLM, enqueue/dequeue.
- [ ] 8.4 Injetar `trace_id` nos logs estruturados (pivô log↔trace).
- [ ] 8.5 Adicionar Collector + Tempo/Jaeger ao compose de observabilidade.
- [ ] 8.6 Tornar sampling e endpoint OTLP configuráveis por env.

## Detalhes de Implementação
Ver ADR-004 e seção "Monitoramento e Observabilidade" do TechSpec. Reusar `app/middleware/request_id.py` e `app/utils/logging_context.py` para correlação. Exportação assíncrona com degradação graciosa.

### Arquivos Relevantes
- `openmemory/api/main.py` — inicialização do tracer na API.
- `openmemory/api/app/workers/*.py` — inicialização nos workers.
- `openmemory/api/app/middleware/request_id.py` — correlação por request_id.
- `openmemory/api/app/utils/logging_context.py` — job_id e injeção de trace_id.
- `openmemory/compose/observability.yml` — Collector + backend de traces.

### Arquivos Dependentes
- `openmemory/api/tests/test_tracing.py` (novo) — testes de spans.

### ADRs Relacionados
- [ADR-004: Observabilidade — tracing distribuído com OpenTelemetry e alertas Prometheus](adrs/adr-004.md) — define a abordagem.

## Entregáveis
- API e workers emitindo traces correlacionados.
- Collector + backend de traces no compose.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Teste de integração validando o encadeamento de spans **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Um request de busca gera spans encadeados (exporter em memória).
  - [ ] `trace_id` aparece nos campos de log da requisição.
  - [ ] Falha do exporter não propaga exceção para o request.
- Testes de integração:
  - [ ] Fluxo MCP→embed→Qdrant produz um trace com os spans esperados.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- 100% das requisições MCP rastreáveis ponta a ponta
