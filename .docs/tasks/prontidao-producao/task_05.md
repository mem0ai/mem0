---
status: pending
title: Política de governança estendida: max_memories, max_memories_action, cold_tier_idle_days
type: backend
complexity: low
dependencies:
  - task_04
---

# Tarefa 5: Política de governança estendida

## Visão Geral
Para impedir crescimento ilimitado por project e habilitar o cold tier, esta tarefa adiciona três campos ao resolver de política existente (global + override): `max_memories`, `max_memories_action` e `cold_tier_idle_days`.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- `DEFAULT_POLICY`, `GovernancePolicySchema` e `EffectivePolicy` DEVEM incluir `max_memories` (int|None, default None), `max_memories_action` (`alert`|`enforce`, default `alert`) e `cold_tier_idle_days` (int, default 180).
- O merge global × override DEVE preservar a semântica existente (override esparso).
- Valores inválidos DEVEM ser rejeitados pela validação Pydantic.
- Os endpoints `PUT /admin/governance/policies` (global e por project) DEVEM aceitar os novos campos sem quebra de contrato.

</requirements>

## Subtarefas
- [ ] 5.1 Adicionar os três campos ao `DEFAULT_POLICY`.
- [ ] 5.2 Estender `GovernancePolicySchema` com validação (action enum; valores >= limites).
- [ ] 5.3 Estender `EffectivePolicy` e `_to_effective`.
- [ ] 5.4 Garantir que o merge e os endpoints de política aceitem os campos.

## Detalhes de Implementação
Ver seção "Design de Implementação > Interfaces Principais" do TechSpec e ADR-005. Alterações concentradas em `app/utils/governance_policy.py`; endpoints já genéricos em `app/routers/governance.py`.

### Arquivos Relevantes
- `openmemory/api/app/utils/governance_policy.py` — default, schema, effective, merge.
- `openmemory/api/app/routers/governance.py` — endpoints de política.

### Arquivos Dependentes
- `openmemory/api/tests/test_governance_policy.py` — cobertura dos novos campos.
- `openmemory/api/tests/test_governance_endpoints.py` — contrato dos endpoints.

### ADRs Relacionados
- [ADR-005: max_memories e cold tier como job types no governance-worker existente](adrs/adr-005.md) — define os campos.

## Entregáveis
- Política estendida e validada (global + override).
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Teste de integração dos endpoints de política com os novos campos **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `max_memories_action` inválido (≠ alert/enforce) é rejeitado.
  - [ ] Override por project sobrepõe `max_memories` global; campos ausentes herdam global.
  - [ ] `cold_tier_idle_days` default = 180 quando omitido.
- Testes de integração:
  - [ ] `PUT /admin/governance/policies/{project}` persiste e relê os novos campos.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Resolver retorna os três campos com semântica global+override correta
