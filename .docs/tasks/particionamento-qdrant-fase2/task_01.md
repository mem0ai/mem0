---
status: completed
title: Modelo de estado de particionamento (migration_state + colunas em projects)
type: backend
complexity: medium
dependencies: []
---

# Modelo de estado de particionamento (migration_state + colunas em projects)

## Visão Geral
Cria o modelo de dados que sustenta toda a Fase 2: a tabela `migration_state` (progresso global da migração e ponteiro da coleção ativa) e as colunas de particionamento por projeto em `projects`. É a fundação lida pelo resolvedor, pelo worker de migração e pelos endpoints administrativos.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir a tabela `migration_state` com os campos da seção "Modelos de Dados" do TechSpec (`source_collection`, `target_collection`, `active_collection`, `dual_write_enabled`, `scroll_cursor`, `status`, `updated_at`).
- `status` DEVE ser um enum com os valores `planned`, `copying`, `validating`, `flipped`, `rolled_back`, `done`.
- A tabela `projects` DEVE ganhar `partition_tier` (enum `shared`/`dedicated`, default `shared`) e `shard_key` (nullable).
- DEVE haver migração Alembic com `upgrade` e `downgrade` simétricos, encadeada após a última revisão existente (`d3c4e5f6a7b8`).
- A migração DEVE rodar tanto em SQLite (dev) quanto em PostgreSQL (produção) sem alteração manual.
</requirements>

## Subtarefas
- [x] 1.1 Definir o enum de status da migração e o enum de `partition_tier` em `models.py`.
- [x] 1.2 Definir o modelo ORM `migration_state` seguindo o padrão de `WriteQueueJob`/`Project`.
- [x] 1.3 Adicionar as colunas `partition_tier` e `shard_key` ao modelo `Project`.
- [x] 1.4 Criar a migração Alembic (upgrade cria tabela/colunas; downgrade inverte exatamente).
- [x] 1.5 Garantir defaults seguros para registros existentes de `projects` (`partition_tier=shared`).

## Detalhes de Implementação
Ver seção "Modelos de Dados" do TechSpec. Seguir o padrão de enums (`class ... (enum.Enum)`) e de tabela com `__table_args__`/índices já usado em `models.py`. A migração segue o encadeamento de `down_revision` existente.

### Arquivos Relevantes
- `openmemory/api/app/models.py` — adicionar enum de status, modelo `migration_state`, colunas em `Project`.
- `openmemory/api/alembic/versions/d3c4e5f6a7b8_add_attempts_and_write_audit.py` — última revisão; nova migração encadeia após ela.
- `openmemory/api/alembic/versions/` — local da nova migração.

### Arquivos Dependentes
- `openmemory/api/app/database.py` — engine/sessão usados pelos testes de schema.
- `openmemory/api/tests/test_postgres_migrations.py` — padrão de teste de migração a estender.

### ADRs Relacionados
- [ADR-003: Migração blue-green com worker dedicado e estado no PostgreSQL](adrs/adr-003.md) — define o estado que esta tarefa materializa.
- [ADR-002: Índice de inquilino com promoção por shard key dedicado](adrs/adr-002.md) — origem das colunas `partition_tier`/`shard_key`.

## Entregáveis
- Enum de status e modelo `migration_state` em `models.py`.
- Colunas `partition_tier` e `shard_key` em `Project`.
- Migração Alembic com upgrade/downgrade simétricos.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de subida do schema (SQLite e PostgreSQL) **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Enum de status aceita apenas os 6 valores definidos e rejeita valor inválido.
  - [ ] `Project` novo recebe `partition_tier=shared` por default quando não informado.
  - [ ] `migration_state` exige `source_collection`/`target_collection`/`active_collection` (não nulos).
- Testes de integração:
  - [ ] `alembic upgrade head` cria `migration_state` e as colunas em `projects` em PostgreSQL sem erro.
  - [ ] `alembic downgrade -1` remove a tabela e as colunas, retornando ao schema anterior.
  - [ ] Registro pré-existente de `projects` (sem as colunas) recebe `partition_tier=shared` após upgrade.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Schema migra e reverte limpo em SQLite e PostgreSQL apenas via Alembic.
- Modelos disponíveis para consumo pelas tarefas 03, 06, 07 e 09.
