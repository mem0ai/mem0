---
status: pending
title: Handler enforce_quota + registro no dispatcher + métricas
type: backend
complexity: medium
dependencies:
  - task_04
  - task_05
---

# Tarefa 6: Handler enforce_quota + registro no dispatcher + métricas

## Visão Geral
Implementa o job que aplica o teto `max_memories` por project. Quando o `memory_count` excede o teto e a ação é `enforce`, quarentena os candidatos menos relevantes (mais antigos/menos acessados) até voltar ao teto; com ação `alert`, apenas emite métrica/log.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir `run_enforce_quota_job(*, project, job_id, limit)` seguindo o contrato `Handler` do governance-worker.
- Com ação `enforce`, DEVE quarentenar candidatos via `QuarantineEngine` até `memory_count <= max_memories`, respeitando pinned e `protected_categories`.
- Com ação `alert`, NÃO DEVE remover nada — apenas métrica/log.
- DEVE ser registrado no dispatcher de handlers e ter entrada de schedule (ex.: `daily`).
- DEVE expor métricas `governance_quota_enforced_total` e `governance_quota_over_limit_projects`.
</requirements>

## Subtarefas
- [ ] 6.1 Implementar a seleção de candidatos (mais antigos/menos acessados) reusando a lógica de TTL.
- [ ] 6.2 Implementar as ações `enforce` (quarentena até o teto) e `alert` (somente métrica).
- [ ] 6.3 Registrar o handler `enforce_quota` no `_default_handlers`.
- [ ] 6.4 Adicionar as métricas em `metrics.py` e emiti-las.
- [ ] 6.5 Garantir respeito a pinned/protected e idempotência.

## Detalhes de Implementação
Ver seção "Interfaces Principais" do TechSpec e ADR-005. Reusar `QuarantineEngine` (`app/utils/quarantine.py`) e a seleção de candidatos de `app/governance/ttl_prune.py`. Catálogo de tamanho em `Project.memory_count`.

### Arquivos Relevantes
- `openmemory/api/app/governance/quota.py` (novo) — handler.
- `openmemory/api/app/workers/governance_worker.py` — `_default_handlers`.
- `openmemory/api/app/utils/quarantine.py` — quarentena reversível.
- `openmemory/api/app/governance/ttl_prune.py` — seleção de candidatos (referência/reuso).
- `openmemory/api/app/utils/metrics.py` — métricas de quota.

### Arquivos Dependentes
- `openmemory/api/tests/test_quota.py` (novo) — testes do handler.

### ADRs Relacionados
- [ADR-005: max_memories e cold tier como job types no governance-worker existente](adrs/adr-005.md) — define comportamento e enforcement assíncrono.

## Entregáveis
- Handler `enforce_quota` registrado e agendado.
- Métricas de quota expostas.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Teste de integração do job via fila/worker **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Ação `alert`: project acima do teto incrementa `over_limit_projects` e não remove nada.
  - [ ] Ação `enforce`: quarentena até `memory_count <= max_memories`.
  - [ ] Memórias pinned e `protected_categories` nunca são quarentenadas.
  - [ ] Project sem `max_memories` (None) é ignorado.
- Testes de integração:
  - [ ] Job enfileirado é processado pelo worker e reduz o excedente.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Nenhum project ultrapassa o teto após execução em modo `enforce`
