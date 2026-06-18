---
status: pending
title: Gate de CI: workflow openmemory-api-ci + wiring no ci-gate.yml
type: infra
complexity: medium
dependencies: []
---

# Tarefa 1: Gate de CI: workflow openmemory-api-ci + wiring no ci-gate.yml

## Visão Geral
Os 39 módulos de teste de `openmemory/api/tests/` não rodam em nenhum pipeline. Esta tarefa cria um workflow reutilizável que executa lint + testes do `openmemory/api` e o integra ao `ci-gate.yml`, o único status check requerido, barrando regressões antes do merge.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir um workflow reutilizável `.github/workflows/openmemory-api-ci.yml` que instala as dependências do `openmemory/api`, roda lint e `pytest openmemory/api/tests`.
- DEVE ser invocado pelo `ci-gate.yml` apenas quando o PR tocar `openmemory/api/**` (filtro `openmemory_api` no job `changes`).
- O job de chamada DEVE constar em `needs` do job `gate`, de forma que o "CI Gate" reflita o resultado.
- A matriz de Python DEVE acompanhar o `ci.yml` existente (3.10–3.12).
- Testes que exigirem Qdrant/PostgreSQL DEVEM ser providos via `services:` ou isolados com mocks/SQLite.
</requirements>

## Subtarefas
- [ ] 1.1 Criar o workflow reutilizável de CI do `openmemory/api` (lint + pytest).
- [ ] 1.2 Adicionar o filtro `openmemory_api` no job `changes` do `ci-gate.yml`.
- [ ] 1.3 Adicionar o call job `openmemory-api` (`uses:` o novo workflow) e incluí-lo em `needs` do `gate`.
- [ ] 1.4 Garantir provisão de serviços ou mocks para testes que exigem infra.
- [ ] 1.5 Validar localmente que a suíte passa antes de confiar no gate.

## Detalhes de Implementação
Ver seção "Sequenciamento de Desenvolvimento" (passo 1) e ADR-002 do TechSpec. O `ci-gate.yml` já segue o padrão filtro→call job→`needs`; replicar para o novo pacote.

### Arquivos Relevantes
- `.github/workflows/ci-gate.yml` — gate agregador; receber filtro + call job + needs.
- `.github/workflows/ci.yml` — referência de matriz/instalação Python.
- `openmemory/api/tests/` — suíte a executar (39 módulos).
- `openmemory/api/pyproject.toml` ou `requirements*.txt` — deps a instalar.

### Arquivos Dependentes
- `.github/workflows/openmemory-api-ci.yml` — novo workflow reutilizável.

### ADRs Relacionados
- [ADR-002: Gate de CI para o openmemory/api via workflow reutilizável no CI Gate](adrs/adr-002.md) — define a estratégia desta tarefa.

## Entregáveis
- Workflow `openmemory-api-ci.yml` funcional e reutilizável.
- `ci-gate.yml` invocando o novo workflow e agregando seu resultado.
- Execução verde da suíte `openmemory/api` em PR de teste.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO — aqui via a própria suíte do openmemory/api executada no gate)**
- Teste de integração: PR que toca `openmemory/api/**` dispara o pipeline e bloqueia em falha **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] A suíte `pytest openmemory/api/tests` roda no workflow e reporta status.
  - [ ] Uma falha proposital em um teste faz o job falhar (vermelho).
- Testes de integração:
  - [ ] PR tocando `openmemory/api/**` aciona o call job; PR que não toca não o aciona (gate não fica pendurado).
  - [ ] O job `gate` falha quando o pipeline do openmemory falha.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Merges com regressão no `openmemory/api` são barrados automaticamente
- O "CI Gate" continua sendo o único status check requerido
