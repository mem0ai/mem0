---
status: pending
title: Documentação: atualizar seção 15 da arquitetura + runbooks
type: docs
complexity: low
dependencies:
  - task_03
  - task_06
  - task_07
  - task_09
  - task_11
---

# Tarefa 12: Documentação — atualizar seção 15 da arquitetura + runbooks

## Visão Geral
Fecha o ciclo documentando o que foi entregue: atualiza a seção 15 ("Estado de implementação") da arquitetura marcando os gaps resolvidos (D2, D3, D7, D8, D9) e cria runbooks de operação e de incidente para os fluxos novos (backup/restore, governança de quota/cold tier, diagnóstico via trace).

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- A seção 15 de `self-hosted-scale-architecture.md` DEVE refletir os gaps fechados (D2 cold tier, D3 max_memories, D7 auth/secrets, D8 rate limit por project, D9 tracing).
- DEVE haver runbooks de: backup/restauração (com RTO/RPO), operação de governança (quota/cold tier), e diagnóstico de incidente via trace/alertas.
- A documentação DEVE referenciar os endpoints, métricas e variáveis de ambiente reais entregues.
- Itens permanentemente fora de escopo (HA, K8s, coleção-por-project, mTLS) DEVEM continuar sinalizados como adiados.
</requirements>

## Subtarefas
- [ ] 12.1 Atualizar a tabela de divergências (seção 15) com o novo estado dos gaps.
- [ ] 12.2 Escrever o runbook de backup/restauração com RTO/RPO medidos.
- [ ] 12.3 Escrever o runbook de governança (quota e cold tier).
- [ ] 12.4 Escrever o runbook de diagnóstico de incidente (alertas + trace).
- [ ] 12.5 Revisar referências cruzadas (endpoints, métricas, env vars).

## Detalhes de Implementação
Ver seção 15 de `openmemory/docs/self-hosted-scale-architecture.md` e o PRD (Métricas de Sucesso). Esta tarefa depende das implementações concluídas para descrever o estado real, não o planejado.

### Arquivos Relevantes
- `openmemory/docs/self-hosted-scale-architecture.md` — seção 15 a atualizar.
- `openmemory/docs/` — destino dos runbooks.
- `.docs/tasks/prontidao-producao/_techspec.md` — fonte de métricas/endpoints/env vars.

### Arquivos Dependentes
- `openmemory/docs/runbooks/*` (novos) — runbooks.

### ADRs Relacionados
- [ADR-001: Prontidão para produção orientada ao alvo LAN interna](adrs/adr-001.md) — escopo e itens adiados.

## Entregáveis
- Seção 15 atualizada com gaps fechados.
- Runbooks de backup/restore, governança e incidente.
- Verificação de links/referências **(OBRIGATÓRIO como teste)**

## Testes
- Testes (verificação documental):
  - [ ] Todos os links internos da seção 15 e dos runbooks resolvem.
  - [ ] Cada gap marcado como fechado tem task/endpoint/métrica correspondente real.
  - [ ] Endpoints e env vars citados existem no código entregue.
- Integração:
  - [ ] Um leitor consegue executar o drill de restauração seguindo apenas o runbook.
- Todos os testes devem passar

## Critérios de Sucesso
- Documentação reflete o estado real pós-implementação
- Runbooks executáveis sem conhecimento tácito
- Itens adiados permanecem explicitamente sinalizados
