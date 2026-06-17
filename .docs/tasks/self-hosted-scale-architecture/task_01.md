---
status: pending
title: Fundação PostgreSQL + PgBouncer (dialeto condicional e migrations)
type: infra
complexity: medium
dependencies: []
---

# Fundação PostgreSQL + PgBouncer (dialeto condicional e migrations)

## Visão Geral
Migra a camada de metadados e fila de SQLite para PostgreSQL acessado via PgBouncer, condicionando o `check_same_thread` ao dialeto e validando as migrations Alembic no novo banco. É a fundação durável que sustenta múltiplos workers e centenas de conexões MCP.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O engine SQLAlchemy DEVE aplicar `connect_args={"check_same_thread": False}` apenas quando o dialeto for SQLite; para PostgreSQL NÃO DEVE passar esse argumento.
- A seleção SQLite vs PostgreSQL DEVE ser feita exclusivamente pela variável `DATABASE_URL`, sem outras ramificações de código.
- As migrations Alembic existentes DEVEM rodar sem alteração de schema contra PostgreSQL (`alembic upgrade head`).
- API e workers DEVEM conectar via PgBouncer em transaction mode, não direto no PostgreSQL.
- O comportamento atual com SQLite DEVE permanecer funcional (modo dev/single-host).
</requirements>

## Subtarefas
- [ ] 1.1 Tornar o `connect_args` do engine condicional ao dialeto detectado em `DATABASE_URL`.
- [ ] 1.2 Validar e ajustar (se necessário) as migrations Alembic para rodar em PostgreSQL.
- [ ] 1.3 Definir o serviço PgBouncer (transaction mode) e o roteamento de API/workers através dele.
- [ ] 1.4 Documentar as variáveis de ambiente de conexão (DATABASE_URL via PgBouncer, credenciais/secret).
- [ ] 1.5 Garantir retrocompatibilidade com SQLite para o cenário dev.

## Detalhes de Implementação
Ver seções "Arquitetura do Sistema" e "Modelos de Dados" do TechSpec. A troca é de backend via `DATABASE_URL`; o Alembic já é driver-agnostic (`env.py` lê `DATABASE_URL`). Apenas o `check_same_thread` é específico de SQLite e deve ser condicionado ao dialeto.

### Arquivos Relevantes
- `openmemory/api/app/database.py` — engine/sessão; condicionar `connect_args` ao dialeto.
- `openmemory/api/alembic/env.py` — já lê `DATABASE_URL`; validar contra PostgreSQL.
- `openmemory/api/alembic/versions/` — migrations a validar no novo banco.

### Arquivos Dependentes
- `openmemory/api/app/models.py` — modelos usados pelo `Base.metadata`; verificar tipos portáveis (UUID, Enum).
- `openmemory/docker-compose.yml` — base para definir PostgreSQL + PgBouncer no stack.

### ADRs Relacionados
- [ADR-003: Fila durável em PostgreSQL com FOR UPDATE SKIP LOCKED e workers em processo separado](../adrs/adr-003.md) — Esta tarefa entrega a base PostgreSQL/PgBouncer.

## Entregáveis
- Engine com `connect_args` condicional ao dialeto.
- Migrations validadas rodando em PostgreSQL.
- Definição de PgBouncer (transaction mode) no stack.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de subida do schema em PostgreSQL **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Engine com `DATABASE_URL` SQLite inclui `check_same_thread=False`.
  - [ ] Engine com `DATABASE_URL` PostgreSQL (`postgresql://...`) NÃO inclui `check_same_thread`.
  - [ ] `DATABASE_URL` ausente/inválido falha de forma descritiva.
- Testes de integração:
  - [ ] `alembic upgrade head` cria todas as tabelas em PostgreSQL (instância de teste/container) sem erro.
  - [ ] `write_queue`, `projects` e `write_audit_logs` existem com os índices esperados após migração.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- A aplicação sobe tanto com SQLite (dev) quanto com PostgreSQL (produção) apenas alternando `DATABASE_URL`.
- API/workers conectam via PgBouncer sem esgotar conexões do PostgreSQL.
