---
status: pending
title: Endpoints /admin/governance/*
type: backend
complexity: medium
dependencies:
  - task_02
  - task_04
  - task_05
---

# Endpoints /admin/governance/*

## Visão Geral
Expõe a superfície de operação da governança para o operador: editar políticas (global e por projeto), enfileirar jobs sob demanda, consultar a trilha de auditoria e reverter memórias da quarentena. Reaproveita o padrão de router administrativo da Fase 2.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVEM existir os endpoints da seção "Endpoints de API" do TechSpec: GET/PUT políticas global, PUT política por projeto, POST enfileirar job por tipo, GET auditoria, POST reverter memória.
- A edição de política global DEVE reutilizar o canal `Config`; a por projeto, a tabela `governance_policies` (com validação Pydantic da task_02).
- O enfileiramento DEVE usar `governance_queue` e retornar `202` com identificador do job.
- A auditoria DEVE ser consultável a partir de `MemoryStatusHistory`, filtrável por projeto/tipo/período.
- A reversão DEVE chamar `QuarantineEngine.revert` e retornar erro adequado se a memória não estiver em quarentena.
- Os endpoints DEVEM seguir o prefixo/injeção de dependência do router administrativo existente.
</requirements>

## Subtarefas
- [ ] 11.1 Implementar GET/PUT da política global e PUT do override por projeto (com validação).
- [ ] 11.2 Implementar POST de enfileiramento de job por tipo (escopo opcional por projeto), resposta `202`.
- [ ] 11.3 Implementar GET de auditoria a partir de `MemoryStatusHistory` com filtros.
- [ ] 11.4 Implementar POST de reversão de memória via `QuarantineEngine`.
- [ ] 11.5 Registrar o router e tratar erros (404/400) seguindo o padrão de `admin.py`.

## Detalhes de Implementação
Ver seção "Endpoints de API" do TechSpec. Seguir o padrão de `routers/admin.py` (prefixo `/admin`, `Depends`, request models Pydantic, `HTTPException`). Consome `resolve_policy`/validação (task_02), `governance_queue` (task_05) e `QuarantineEngine` (task_04). O endpoint de qualidade (`/quality`) pertence à task_12.

### Arquivos Relevantes
- `openmemory/api/app/routers/admin.py` — padrão de router administrativo a estender (ou novo router `governance.py` montado no mesmo prefixo).
- `openmemory/api/app/utils/governance_policy.py` — leitura/escrita/validação de política (task_02).
- `openmemory/api/app/utils/governance_queue.py` — `enqueue` (task_05).
- `openmemory/api/app/utils/quarantine.py` — `revert` (task_04).
- `openmemory/api/app/models.py` — `MemoryStatusHistory`, `governance_policies`.

### Arquivos Dependentes
- `openmemory/api/app/main.py` — registro do router (se novo arquivo).
- `openmemory/api/tests/test_migration_endpoints.py` — padrão de teste de endpoints a espelhar.

### ADRs Relacionados
- [ADR-005: Políticas — Config global + override por projeto](adrs/adr-005.md) — superfície de edição de política.
- [ADR-003: Estado `quarantined` com retenção do vetor e expurgo diferido](adrs/adr-003.md) — reversão a partir da quarentena.

## Entregáveis
- Endpoints `/admin/governance/*` (políticas, jobs, auditoria, reversão).
- Request/response models Pydantic.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração da API (cliente de teste FastAPI) **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] PUT de política global inválida retorna `400` (validação).
  - [ ] PUT de override por projeto persiste em `governance_policies`.
  - [ ] POST de enfileirar job retorna `202` e cria registro em `governance_jobs`.
  - [ ] GET de auditoria filtra por projeto/tipo/período.
  - [ ] POST de reverter memória não-quarentenada retorna `404`/`409` adequado.
- Testes de integração:
  - [ ] Fluxo: definir política por projeto → enfileirar `dedup` → consultar auditoria após processamento → reverter uma memória quarentenada.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Operador consegue editar política, enfileirar jobs, auditar e reverter
- Padrão do router administrativo respeitado
