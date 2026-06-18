---
status: pending
title: Migration de modelos: enum enforce_quota/cold_tier, Project.last_activity_at, intervalo monthly
type: backend
complexity: medium
dependencies:
  - task_01
---

# Tarefa 4: Migration de modelos para quota e cold tier

## Visão Geral
A Fase 2 introduz dois novos job types de governança e precisa rastrear inatividade por project. Esta tarefa prepara o modelo de dados: estende o enum `GovernanceJobType`, adiciona `Project.last_activity_at` e o intervalo `monthly` ao scheduler.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O enum `GovernanceJobType` DEVE incluir `enforce_quota` e `cold_tier`.
- `Project` DEVE ter `last_activity_at` (datetime, nullable) alimentado pelo write path / access logs.
- `SCHEDULE_INTERVALS` DEVE incluir `monthly`.
- DEVE haver migration Alembic compatível com SQLite (dev) e PostgreSQL (prod), seguindo o dialeto condicional existente.
- A migration DEVE ser reversível (downgrade).
</requirements>

## Subtarefas
- [ ] 4.1 Estender o enum `GovernanceJobType` com os dois valores.
- [ ] 4.2 Adicionar a coluna `last_activity_at` ao modelo `Project`.
- [ ] 4.3 Alimentar `last_activity_at` no caminho de escrita / atualização de acesso.
- [ ] 4.4 Adicionar `monthly` a `SCHEDULE_INTERVALS`.
- [ ] 4.5 Criar a migration Alembic (upgrade/downgrade) compatível com os dois dialetos.

## Detalhes de Implementação
Ver seção "Modelos de Dados" do TechSpec e ADR-005. Seguir o padrão de migrations em `openmemory/api/alembic/versions/` e o dialeto condicional de `app/database.py`. O upsert de project já existe no write worker (`_upsert_project`).

### Arquivos Relevantes
- `openmemory/api/app/models.py` — enum e modelo `Project`.
- `openmemory/api/app/workers/governance_worker.py` — `SCHEDULE_INTERVALS`.
- `openmemory/api/app/workers/write_worker.py` — `_upsert_project` (alimentar `last_activity_at`).
- `openmemory/api/alembic/versions/` — nova revisão.

### Arquivos Dependentes
- `openmemory/api/tests/test_postgres_migrations.py` — cobertura de migration.
- `openmemory/api/tests/test_governance_models.py` — cobertura do enum.

### ADRs Relacionados
- [ADR-005: max_memories e cold tier como job types no governance-worker existente](adrs/adr-005.md) — motiva os novos valores.

## Entregáveis
- Enum e modelo estendidos; migration reversível.
- `last_activity_at` populado em escrita/acesso.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Teste de integração de upgrade/downgrade da migration **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `GovernanceJobType` aceita `enforce_quota` e `cold_tier`.
  - [ ] `SCHEDULE_INTERVALS["monthly"]` resolve para 30 dias.
  - [ ] Escrita atualiza `last_activity_at` do project.
- Testes de integração:
  - [ ] `alembic upgrade head` e `downgrade -1` funcionam em SQLite e PostgreSQL.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Migration aplica e reverte sem perda em ambos os dialetos
