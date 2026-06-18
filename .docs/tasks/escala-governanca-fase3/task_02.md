---
status: pending
title: Resolvedor de política efetiva (global + override)
type: backend
complexity: medium
dependencies:
  - task_01
---

# Resolvedor de política efetiva (global + override)

## Visão Geral
Implementa a resolução da política de governança aplicável a um projeto, combinando o padrão global (`Config(key="governance")`) com o override esparso por projeto (`governance_policies`). É o ponto único consumido pelo agendador, pelos jobs e pelos endpoints para saber "o que aplicar e quando".

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir um tipo `EffectivePolicy` com os campos da seção "Interfaces Principais" do TechSpec (TTL por idade e por ociosidade, janela de quarentena, flag de consolidação, limiar de similaridade, regra de contradição, categorias protegidas, agendas).
- `resolve_policy(project)` DEVE fazer o merge global ⟵ override, com o override sobrescrevendo apenas os campos presentes.
- Campos ausentes no global DEVEM cair em defaults conservadores definidos no código.
- A leitura/escrita do documento global DEVE reutilizar o canal de `Config` existente.
- A entrada de política DEVE ser validada (modelo Pydantic) ao ser persistida.
</requirements>

## Subtarefas
- [ ] 2.1 Definir `EffectivePolicy` e o modelo Pydantic de validação dos campos da política.
- [ ] 2.2 Implementar a leitura do global via `Config(key="governance")` com defaults conservadores.
- [ ] 2.3 Implementar a leitura do override por projeto em `governance_policies`.
- [ ] 2.4 Implementar o merge global ⟵ override (precedência e campos ausentes).
- [ ] 2.5 Expor `resolve_policy(project) -> EffectivePolicy` como ponto único de consumo.

## Detalhes de Implementação
Ver seções "Interfaces Principais" e "Modelos de Dados" do TechSpec e o [ADR-005](adrs/adr-005.md). Reutilizar `get_config_from_db`/setter de `routers/config.py`. Novo módulo `openmemory/api/app/utils/governance_policy.py`.

### Arquivos Relevantes
- `openmemory/api/app/utils/governance_policy.py` — **novo**: `EffectivePolicy`, `resolve_policy`, validação.
- `openmemory/api/app/routers/config.py` — padrão de `Config` (get/set, `deep_update`).
- `openmemory/api/app/models.py` — `Config`, `governance_policies` (da task_01).

### Arquivos Dependentes
- `openmemory/api/app/workers/governance_worker.py` — consumirá `resolve_policy` (tasks 06–10).
- `openmemory/api/app/routers/admin.py` — endpoints de política (task_11).

### ADRs Relacionados
- [ADR-005: Políticas — Config JSON global + tabela de override por projeto](adrs/adr-005.md) — define o modelo de duas camadas e o merge.

## Entregáveis
- Módulo `governance_policy.py` com `EffectivePolicy` e `resolve_policy`.
- Modelo Pydantic de validação da política.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de leitura combinada Config + tabela **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Projeto sem override herda 100% do global.
  - [ ] Override sobrescreve só os campos presentes; demais herdam do global.
  - [ ] Campo ausente no global cai no default conservador esperado.
  - [ ] Política inválida (ex.: `similarity_threshold` fora de [0,1]) é rejeitada na validação.
  - [ ] `contradiction_tiebreak` aceita apenas `recency`/`confidence`.
- Testes de integração:
  - [ ] `resolve_policy` lê Config global + override do banco e retorna a política mesclada.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Merge global ⟵ override correto e determinístico
- Defaults conservadores aplicados quando faltam campos
