---
status: pending
title: Deploy do serviço governance-worker
type: infra
complexity: medium
dependencies:
  - task_06
  - task_07
  - task_08
  - task_09
  - task_10
---

# Deploy do serviço governance-worker

## Visão Geral
Operacionaliza a governança no ambiente Docker Swarm: adiciona o serviço `governance-worker` ao stack, com o papel agendador rodando como singleton (`replicas: 1`) para não duplicar enfileiramento, reaproveitando a imagem e as variáveis de ambiente dos workers existentes.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O `docker-stack.yml` DEVE definir o serviço `governance-worker` reutilizando a imagem `mem0/openmemory-mcp` e o comando `python -m app.workers.governance_worker`.
- O papel agendador DEVE rodar como singleton (`replicas: 1`); o processamento pode escalar conforme necessário.
- O serviço DEVE receber as mesmas variáveis de ambiente de banco/Qdrant/Redis dos workers existentes e `RUN_EMBEDDED_WORKER: "false"`.
- O serviço DEVE ter `restart_policy` consistente com os demais workers.
- A configuração DEVE ser validável por teste (estrutura do compose), como os testes de compose existentes.
</requirements>

## Subtarefas
- [ ] 13.1 Adicionar o serviço `governance-worker` ao `docker-stack.yml` seguindo o padrão do `write-worker`.
- [ ] 13.2 Configurar o papel agendador como singleton (`replicas: 1`) e variáveis de ambiente.
- [ ] 13.3 Definir `restart_policy` e dependências de rede (Postgres/Qdrant/Redis).
- [ ] 13.4 Documentar/validar o comando de escala do processamento (à parte do agendador).

## Detalhes de Implementação
Ver seções "Análise de Impacto" (Deploy) e "Sequenciamento de Desenvolvimento" (passo 13) do TechSpec e o [ADR-002](adrs/adr-002.md). Espelhar o serviço `openmemory-write-worker` do `docker-stack.yml` (linhas ~54–66). Atenção ao singleton do agendador para não duplicar enfileiramento.

### Arquivos Relevantes
- `openmemory/docker-stack.yml` — adicionar o serviço `governance-worker`.
- `openmemory/api/app/workers/governance_worker.py` — alvo do `command` (tasks 05/06).

### Arquivos Dependentes
- `openmemory/api/tests/test_docker_compose.py` — padrão de teste de estrutura do compose a espelhar.
- `openmemory/api/tests/test_bootstrap_scale.py` — referência de validação de stack de escala.

### ADRs Relacionados
- [ADR-002: Worker de governança dedicado com loop temporal interno sobre fila PostgreSQL](adrs/adr-002.md) — exige agendador singleton e serviço dedicado.

## Entregáveis
- Serviço `governance-worker` no `docker-stack.yml` (agendador `replicas: 1`).
- Testes de estrutura do compose/stack **(OBRIGATÓRIO)**
- Testes de integração da definição do serviço **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] O serviço `governance-worker` existe no stack com o comando correto.
  - [ ] O papel agendador está com `replicas: 1`.
  - [ ] Variáveis de ambiente de banco/Qdrant/Redis e `RUN_EMBEDDED_WORKER=false` presentes.
  - [ ] `restart_policy` definida consistente com os demais workers.
- Testes de integração:
  - [ ] Parse/validação do `docker-stack.yml` reconhece o novo serviço sem quebrar os existentes.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Serviço `governance-worker` definido e validado, agendador como singleton
- Sem regressão nos serviços existentes do stack
