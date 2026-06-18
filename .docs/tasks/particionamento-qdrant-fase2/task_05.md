---
status: completed
title: Dual-write condicional no write-worker (blue + green durante a janela)
type: backend
complexity: medium
dependencies:
  - task_04
---

# Dual-write condicional no write-worker (blue + green durante a janela)

## Visão Geral
Faz o write-worker replicar cada escrita também na coleção destino enquanto a flag `dual_write_enabled` estiver ligada, garantindo que a coleção green não perca frescor durante a migração. A replicação é idempotente por ID de ponto.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- Quando `dual_write_enabled` for verdadeiro, a escrita DEVE ser aplicada na coleção ativa E na coleção destino.
- A replicação na destino DEVE ser idempotente por ID de ponto (reexecução não duplica).
- Com `dual_write_enabled` falso, o comportamento DEVE ser idêntico ao atual (uma única coleção).
- Falha na escrita da destino DEVE ser registrada (log estruturado/auditoria) sem corromper o estado da coleção ativa.
- O lag da fila de escrita NÃO DEVE estourar a meta da Fase 1 por causa do dual-write (operação adicional contida).
</requirements>

## Subtarefas
- [x] 5.1 Ler a flag `dual_write_enabled` e a coleção destino do estado de migração.
- [x] 5.2 Aplicar a escrita também na destino quando habilitado, reutilizando os mesmos IDs de ponto.
- [x] 5.3 Tratar falha de replicação com log estruturado sem abortar a escrita principal.
- [x] 5.4 Emitir métrica de erro de dual-write.
- [x] 5.5 Garantir caminho desligado idêntico ao atual.

## Detalhes de Implementação
Ver seção "Design de Implementação" do TechSpec (dual-write idempotente por ID). O ponto de injeção é após o `add` normal no `write_worker`. A coleção destino e a flag vêm de `migration_state` (via resolvedor/leitura de estado).

### Arquivos Relevantes
- `openmemory/api/app/workers/write_worker.py` — ponto de injeção do dual-write.
- `openmemory/api/app/utils/partitioning.py` — coleção ativa/destino e flag.
- `openmemory/api/app/utils/metrics.py` — definir contador de erro de dual-write.

### Arquivos Dependentes
- `openmemory/api/app/utils/write_queue.py` — fila consumida pelo worker.
- `openmemory/api/app/models.py` — `migration_state` (flag/destino).

### ADRs Relacionados
- [ADR-003: Migração blue-green com worker dedicado e estado no PostgreSQL](adrs/adr-003.md) — dual-write como mecanismo de frescor da green.

## Entregáveis
- Dual-write condicional idempotente no write-worker.
- Métrica `dual_write_errors`.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de escrita dupla blue+green **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Com flag ligada, o `add` é chamado para coleção ativa e destino com o mesmo ID.
  - [ ] Com flag desligada, o `add` ocorre só na coleção ativa.
  - [ ] Falha na destino incrementa `dual_write_errors` e não levanta exceção para a escrita principal.
- Testes de integração:
  - [ ] Escrita com dual-write ligado aparece em ambas as coleções (consulta confirma paridade).
  - [ ] Reprocessar o mesmo job (mesmo ID) não duplica pontos na destino.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Green permanece fresca durante a janela; reexecução não duplica.
- Sem regressão no caminho com dual-write desligado.
