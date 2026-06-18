---
status: pending
title: Job de poda por TTL (idade e último acesso)
type: backend
complexity: medium
dependencies:
  - task_02
  - task_04
  - task_05
---

# Job de poda por TTL (idade e último acesso)

## Visão Geral
Segundo guarda-corpo de volume: um handler que poda memórias **antigas E sem acesso recente** segundo a política efetiva do projeto, enviando-as para quarentena reversível. Usar idade **e** último acesso evita apagar conhecimento antigo ainda consultado.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O handler `ttl_prune` DEVE selecionar memórias cuja idade exceda `ttl_max_age_days` E cujo último acesso exceda `ttl_idle_days`, conforme `resolve_policy`.
- As memórias selecionadas DEVEM ir para quarentena via `QuarantineEngine` (reversível).
- Memórias pinadas e de categorias protegidas NÃO DEVEM ser podadas.
- O último acesso DEVE ser derivado de `memory_access_logs` (`accessed_at`).
- O job DEVE ser idempotente e processar em lotes com teto configurável.
- O job DEVE ser registrado como handler de `job_type=ttl_prune`.
</requirements>

## Subtarefas
- [ ] 8.1 Obter a política efetiva do escopo (`ttl_max_age_days`, `ttl_idle_days`, categorias protegidas).
- [ ] 8.2 Selecionar candidatos por idade (`created_at`) E ociosidade (último `accessed_at`).
- [ ] 8.3 Excluir pinadas e categorias protegidas dos candidatos.
- [ ] 8.4 Quarentenar os candidatos via `QuarantineEngine`.
- [ ] 8.5 Registrar o handler em `job_type=ttl_prune` e garantir idempotência/teto de lote.

## Detalhes de Implementação
Ver seção "Sequenciamento de Desenvolvimento" (passo 8) do TechSpec e o [ADR-001](adrs/adr-001.md). O último acesso vem de `MemoryAccessLog` (`models.py` ~linhas 264–276, índice `idx_access_memory_time`); idade vem de `created_at`. Consome `resolve_policy` (task_02) e o motor (task_04).

### Arquivos Relevantes
- `openmemory/api/app/governance/ttl_prune.py` — **novo**: handler do job de TTL.
- `openmemory/api/app/models.py` — `Memory.created_at`, `MemoryAccessLog.accessed_at`.
- `openmemory/api/app/utils/governance_policy.py` — `resolve_policy` (task_02).
- `openmemory/api/app/utils/quarantine.py` — `QuarantineEngine` (task_04).
- `openmemory/api/app/workers/governance_worker.py` — registro do handler.

### Arquivos Dependentes
- `openmemory/api/app/utils/metrics.py` — `governance_pruned_total` (task_12).

### ADRs Relacionados
- [ADR-001: Governança automática com rede de segurança, faseada](adrs/adr-001.md) — poda por idade E uso, conservadora e reversível.
- [ADR-005: Políticas — Config global + override por projeto](adrs/adr-005.md) — origem dos parâmetros de TTL.

## Entregáveis
- Handler do job de TTL registrado no worker.
- Seleção por idade E último acesso, com exclusão de pinadas/protegidas.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de poda ponta a ponta **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Memória antiga E ociosa além dos limites é selecionada para quarentena.
  - [ ] Memória antiga MAS acessada recentemente NÃO é podada.
  - [ ] Memória recente NÃO é podada mesmo que ociosa.
  - [ ] Pinada/categoria protegida nunca é podada.
  - [ ] Limites vêm da política efetiva (override por projeto respeitado).
- Testes de integração:
  - [ ] Job `ttl_prune` processado quarentena os candidatos corretos e os remove da busca (task_03).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Poda só atinge memórias antigas E ociosas, nunca pinadas/protegidas
- Parâmetros respeitam a política efetiva por projeto
