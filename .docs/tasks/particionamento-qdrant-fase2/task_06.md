---
status: completed
title: Worker de migração - cópia blue-green com checkpoint
type: backend
complexity: high
dependencies:
  - task_01
  - task_02
---

# Worker de migração - cópia blue-green com checkpoint

## Visão Geral
Implementa o worker de migração dedicado que provisiona a coleção green (já com índice de inquilino) e copia os pontos da blue por `scroll` paginado + `upsert` em batch, registrando o cursor em `migration_state` para retomada idempotente. Isola a carga pesada de cópia do caminho de escrita.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O worker DEVE provisionar a coleção green com índice de inquilino e demais índices criados ANTES da carga.
- A cópia DEVE percorrer a blue por `scroll` paginado e gravar na green por `upsert` em batch, preservando IDs de ponto.
- O progresso DEVE ser persistido em `migration_state.scroll_cursor` e a cópia DEVE retomar do cursor após reinício.
- A cópia DEVE ser idempotente (reexecução a partir do cursor não duplica pontos).
- O worker DEVE rodar como processo/serviço separado do write-worker (entrypoint próprio, modelo `python -m`).
- O worker DEVE atualizar `status` de migração (`copying`, `validating`) conforme avança.
</requirements>

## Subtarefas
- [x] 6.1 Provisionar a coleção green com índices criados antes da carga (via provider da tarefa 02).
- [x] 6.2 Implementar a cópia `scroll`→`upsert` em batch preservando IDs.
- [x] 6.3 Persistir e ler o `scroll_cursor` em `migration_state` (checkpoint).
- [x] 6.4 Implementar retomada idempotente a partir do cursor.
- [x] 6.5 Criar o entrypoint do worker (modelo `python -m app.workers...`) e o serviço no compose de escala.
- [x] 6.6 Atualizar o `status` da migração ao longo do processo.

## Detalhes de Implementação
Ver seção "Design de Implementação" do TechSpec (blue-green, checkpoint). Seguir o padrão do entrypoint standalone existente (`app/workers/__main__.py` / `docker-compose.scale.yml`). A cópia usa `client.scroll` + `vector_store.insert/upsert`.

### Arquivos Relevantes
- `openmemory/api/app/workers/migration_worker.py` — novo worker de migração.
- `openmemory/api/app/workers/__main__.py` — padrão de entrypoint standalone a espelhar.
- `mem0/vector_stores/qdrant.py` — `insert`/`upsert`/criação de coleção (tarefa 02).
- `openmemory/docker-compose.scale.yml` — adicionar serviço do migration-worker.

### Arquivos Dependentes
- `openmemory/api/app/models.py` — `migration_state` (cursor/status).
- `openmemory/api/app/utils/metrics.py` — métrica de progresso de cópia.

### ADRs Relacionados
- [ADR-003: Migração blue-green com worker dedicado e estado no PostgreSQL](adrs/adr-003.md) — define este worker e o checkpoint.
- [ADR-002: Índice de inquilino com promoção por shard key](adrs/adr-002.md) — green criada com índice antes da carga.

## Entregáveis
- `migration_worker.py` com provisão da green e cópia com checkpoint.
- Entrypoint standalone + serviço no compose de escala.
- Métrica de progresso de cópia.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de cópia/retomada **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] A green é criada com os índices antes de qualquer `upsert`.
  - [ ] O cursor é persistido após cada batch e lido na inicialização.
  - [ ] Retomada a partir de um cursor intermediário não reprocessa pontos já copiados.
- Testes de integração:
  - [ ] Cópia completa blue→green de N pontos resulta em contagem igual e IDs preservados.
  - [ ] Interromper a cópia no meio e reiniciar conclui sem duplicar (idempotência).
  - [ ] `status` transita `planned`→`copying`→`validating` corretamente.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Base copiada para a green de forma retomável e idempotente, sem afetar o write-worker.
