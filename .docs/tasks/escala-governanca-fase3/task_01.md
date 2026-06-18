---
status: pending
title: Modelos e migrations de governança
type: backend
complexity: medium
dependencies: []
---

# Modelos e migrations de governança

## Visão Geral
Cria a fundação de dados de toda a Fase 3: o estado `quarantined` no enum de memória, a coluna `quarantined_at` e as três tabelas de governança (`governance_jobs`, `governance_policies`, `governance_schedule`). É a base lida pelo resolvedor de política, pelo motor de quarentena, pelo worker e pelos endpoints.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O enum `MemoryState` DEVE ganhar o valor `quarantined`, distinto de `archived` e `deleted`.
- A tabela `memories` DEVE ganhar a coluna `quarantined_at` (DateTime, nullable, indexada).
- DEVEM existir as tabelas `governance_jobs`, `governance_policies` e `governance_schedule` com os campos da seção "Modelos de Dados" do TechSpec.
- `governance_jobs.job_type` DEVE ser enum (`dedup`, `ttl_prune`, `consolidate`, `purge`) e `status` enum (`queued`, `processing`, `done`, `failed`).
- DEVE haver migração Alembic com `upgrade`/`downgrade` simétricos, encadeada após a revisão `e4d5f6a7b8c9`, funcional em SQLite (dev) e PostgreSQL (prod).
- Registros existentes de `memories` NÃO DEVEM ser afetados (default de estado preservado).
</requirements>

## Subtarefas
- [ ] 1.1 Adicionar `quarantined` ao enum `MemoryState` e a coluna `quarantined_at` ao modelo `Memory`.
- [ ] 1.2 Definir o modelo ORM `governance_jobs` seguindo o padrão de `WriteQueueJob`.
- [ ] 1.3 Definir os modelos `governance_policies` (PK/FK `project_name`) e `governance_schedule` (PK composta `job_type`+`scope`).
- [ ] 1.4 Criar a migração Alembic encadeada (upgrade cria enum/coluna/tabelas; downgrade inverte exatamente), com tratamento de enum para PostgreSQL e SQLite.
- [ ] 1.5 Garantir compatibilidade com registros existentes (sem reescrever estado das memórias atuais).

## Detalhes de Implementação
Ver seção "Modelos de Dados" do TechSpec. Seguir o padrão de enums (`class ...(enum.Enum)`) e de tabelas com índices já usado em `models.py`; a migração espelha o tratamento de enum dialeto-aware da revisão `e4d5f6a7b8c9`.

### Arquivos Relevantes
- `openmemory/api/app/models.py` — `MemoryState` (linhas 31–35), `Memory`, `WriteQueueJob` (padrão de fila), `MemoryAccessLog`.
- `openmemory/api/alembic/versions/e4d5f6a7b8c9_add_partitioning_state.py` — última revisão; nova migração encadeia após ela.
- `openmemory/api/alembic/versions/` — local da nova migração.

### Arquivos Dependentes
- `openmemory/api/app/database.py` — engine/sessão usados nos testes de schema.
- `openmemory/api/tests/test_postgres_migrations.py` — padrão de teste de migração a estender.
- `openmemory/api/tests/test_partitioning_models.py` — padrão de teste de modelo a espelhar.

### ADRs Relacionados
- [ADR-003: Estado `quarantined` dedicado com retenção do vetor e expurgo diferido](adrs/adr-003.md) — origem do estado e da coluna.
- [ADR-002: Worker de governança dedicado sobre fila PostgreSQL](adrs/adr-002.md) — origem de `governance_jobs`/`governance_schedule`.
- [ADR-005: Políticas — Config global + override por projeto](adrs/adr-005.md) — origem de `governance_policies`.

## Entregáveis
- `quarantined` no enum + `quarantined_at` em `Memory`.
- Modelos `governance_jobs`, `governance_policies`, `governance_schedule`.
- Migração Alembic com upgrade/downgrade simétricos.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de subida do schema (SQLite e PostgreSQL) **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Enum `MemoryState` aceita `quarantined` e não quebra os valores existentes.
  - [ ] Criar `Memory` com `state=quarantined` e `quarantined_at` definido persiste corretamente.
  - [ ] `governance_jobs` rejeita `job_type`/`status` fora do enum.
  - [ ] `governance_policies` exige `project_name` único (PK) e aceita `overrides` JSON.
  - [ ] `governance_schedule` aceita PK composta (`job_type`,`scope`) e atualiza `last_run_at`.
- Testes de integração:
  - [ ] `alembic upgrade head` cria enum/coluna/tabelas em SQLite e em PostgreSQL.
  - [ ] `alembic downgrade -1` remove exatamente o que foi criado, sem resíduos.
  - [ ] Memórias pré-existentes mantêm seu estado após o upgrade.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Schema sobe e desce em SQLite e PostgreSQL sem intervenção manual
- Nenhuma regressão em modelos/migrations existentes da Fase 2
