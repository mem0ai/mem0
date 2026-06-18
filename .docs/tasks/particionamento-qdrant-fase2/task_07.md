---
status: completed
title: Validação, flip atômico e rollback (endpoints de migração)
type: backend
complexity: high
dependencies:
  - task_05
  - task_06
---

# Validação, flip atômico e rollback (endpoints de migração)

## Visão Geral
Implementa a etapa de corte da migração: validação de paridade entre blue e green, o flip atômico do ponteiro `active_collection` (com invalidação de cache do resolvedor) e o rollback para a blue. Expõe os endpoints administrativos que orquestram start/flip/rollback.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- A validação DEVE comparar contagem e amostras entre blue e green antes de permitir o flip.
- O flip DEVE alterar atomicamente `active_collection` em `migration_state` e invalidar o cache do `PartitionResolver`.
- O rollback DEVE repontar `active_collection` para a blue e ser executável após o flip.
- Os endpoints `/admin/migration/start`, `/admin/migration/flip` e `/admin/migration/rollback` DEVEM ser idempotentes quanto a chamadas repetidas no mesmo estado.
- O flip NÃO DEVE causar perda de escrita: dual-write permanece ligado até o flip; só é desligado após a green virar ativa.
</requirements>

## Subtarefas
- [x] 7.1 Implementar a validação de paridade (contagem) blue vs green.
- [x] 7.2 Implementar o flip atômico de `active_collection` + invalidação de cache.
- [x] 7.3 Implementar o rollback para a blue.
- [x] 7.4 Criar o router administrativo com start/flip/rollback e registrá-lo em `main.py`.
- [x] 7.5 Definir a ordem segura: validar → flip → desligar dual-write.

## Detalhes de Implementação
Ver seções "Endpoints de API" e "Design de Implementação" (validação antes do corte; flip atômico) do TechSpec. Criar um novo `routers/admin.py` seguindo o padrão dos routers existentes e registrá-lo via `app.include_router`.

### Arquivos Relevantes
- `openmemory/api/app/routers/admin.py` — novo router de migração (start/flip/rollback).
- `openmemory/api/main.py` — registro do router (`include_router`).
- `openmemory/api/app/utils/partitioning.py` — `invalidate()` chamado no flip.
- `openmemory/api/app/models.py` — `migration_state` (active_collection/status/flag).

### Arquivos Dependentes
- `openmemory/api/app/routers/__init__.py` — índice de routers.
- `openmemory/api/app/workers/write_worker.py` — flag de dual-write alterada após flip.

### ADRs Relacionados
- [ADR-003: Migração blue-green com worker dedicado e estado no PostgreSQL](adrs/adr-003.md) — define validação, flip e reversibilidade.

## Entregáveis
- Validação de paridade blue/green.
- Flip atômico com invalidação de cache e rollback.
- Router `/admin/migration/*` registrado.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração do ciclo start→flip→rollback **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Validação falha (bloqueia flip) quando contagem blue ≠ green.
  - [ ] Flip altera `active_collection` e chama `invalidate()` exatamente uma vez.
  - [ ] `/admin/migration/flip` chamado duas vezes no mesmo estado é idempotente (não corrompe estado).
- Testes de integração:
  - [ ] Ciclo completo: start → cópia (mock/green pronta) → validação OK → flip → leitura passa a ocorrer na green.
  - [ ] Rollback após flip repontar para a blue e leitura volta à blue.
  - [ ] Dual-write permanece ligado até o flip e é desligado somente depois.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Corte da migração sem downtime e reversível, validado antes do flip.
