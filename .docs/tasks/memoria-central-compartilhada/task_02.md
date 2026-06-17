---
status: completed
title: Tabela e catálogo de projetos (modelo + upsert idempotente)
type: backend
complexity: low
dependencies: []
---

# Tabela e catálogo de projetos (modelo + upsert idempotente)

## Visão Geral
Criar o catálogo interno de projetos no banco do OpenMemory, com uma tabela `projects` e uma função de upsert idempotente. O catálogo é materializado automaticamente na primeira escrita de cada projeto (chamado pelo worker), suportando a auto-criação/auto-gestão de espaços sem administração manual.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir uma tabela `projects` com pelo menos `name` (identificador único), `created_at` e `first_seen_hostname`.
- DEVE haver uma função de upsert idempotente: registrar o projeto na primeira vez e não duplicar em chamadas subsequentes.
- A criação da tabela DEVE seguir o mecanismo de schema/migração já usado pelo OpenMemory (Alembic + `Base.metadata`).
- O upsert NÃO DEVE lançar erro quando o projeto já existe.
</requirements>

## Subtarefas
- [ ] 02.1 Definir o modelo `Project` (tabela `projects`) no padrão dos modelos existentes.
- [ ] 02.2 Gerar a migração Alembic correspondente.
- [ ] 02.3 Implementar a função de upsert idempotente do projeto.
- [ ] 02.4 Cobrir com testes o upsert (criação e idempotência).

## Detalhes de Implementação
Seguir o padrão de modelos em `openmemory/api/app/models.py` (UUID/colunas, timestamps UTC) e o fluxo de migração em `openmemory/api/alembic/`. A tabela é criada no startup via `Base.metadata.create_all` (ver `openmemory/api/main.py`). A função de upsert pode residir em um util de catálogo. Ver seção "Modelos de Dados → ProjectCatalog" do TechSpec.

### Arquivos Relevantes
- `openmemory/api/app/models.py` — adicionar o modelo `Project`.
- `openmemory/api/alembic/versions/` — nova migração da tabela `projects`.
- `openmemory/api/app/database.py` — engine/SessionLocal/Base reutilizados.

### Arquivos Dependentes
- `openmemory/api/main.py` — `Base.metadata.create_all` cobre a nova tabela no startup.
- Worker da tarefa 06 — chamará o upsert na primeira escrita de cada projeto.

### ADRs Relacionados
- [ADR-002: Espaços auto-criados e auto-gerenciados por projeto](../adrs/adr-002.md) — Catálogo interno sem administração manual.

## Entregáveis
- Modelo `Project` + migração Alembic da tabela `projects`.
- Função de upsert idempotente de projeto.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para criação de tabela e upsert **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Upsert de projeto inexistente cria o registro com `name` e `first_seen_hostname`.
  - [ ] Upsert de projeto existente não cria duplicata e não lança erro.
  - [ ] `created_at` é preenchido na criação.
- Testes de integração:
  - [ ] Após `create_all`, a tabela `projects` existe e aceita upsert via sessão real.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Tabela `projects` criada e upsert idempotente funcionando
- Sem duplicação de projetos em escritas repetidas
