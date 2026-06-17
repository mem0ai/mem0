---
status: pending
title: Write worker como processo separado (entrypoint + gate do startup)
type: backend
complexity: medium
dependencies:
  - task_02
---

# Write worker como processo separado (entrypoint + gate do startup)

## Visão Geral
Extrai o write worker do processo da API para um serviço independente, com entrypoint próprio, permitindo escalar a escrita por número de réplicas sem acoplar ao ciclo de vida da API. O hook de startup embutido passa a ser opcional (gated por env) para preservar o modo dev/single-host.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir um entrypoint executável (ex.: `python -m app.workers.write_worker`) que instancia e roda o `WriteWorker.run()` como processo independente.
- O startup hook embutido na API DEVE ser condicionado por variável de ambiente (ex.: `RUN_EMBEDDED_WORKER`), desabilitado por padrão em produção.
- O ack imediato (`queued` + `job_id`) e a lógica de retry/backoff existentes DEVEM ser preservados.
- O worker separado e a API DEVEM compartilhar o mesmo `DATABASE_URL`.
- O encerramento DEVE ser gracioso (drenar/parar sem perder jobs em `processing`).
</requirements>

## Subtarefas
- [ ] 3.1 Criar o entrypoint do worker como processo independente.
- [ ] 3.2 Condicionar o `@app.on_event("startup")`/`shutdown` do worker embutido a uma env flag.
- [ ] 3.3 Garantir encerramento gracioso (sinal de stop + await da task).
- [ ] 3.4 Definir o serviço de worker no stack com réplicas configuráveis.
- [ ] 3.5 Validar que API e worker compartilham a mesma fila/banco.

## Detalhes de Implementação
Ver seção "Arquitetura do Sistema" (componente `mem0-write-worker`) e "Sequenciamento de Desenvolvimento" do TechSpec. O `WriteWorker` já possui `start()`/`stop()`/`run()`; a tarefa adiciona o entrypoint e o gate de startup, sem reescrever a lógica de processamento.

### Arquivos Relevantes
- `openmemory/api/app/workers/write_worker.py` — alvo do entrypoint (`run()` já existe).
- `openmemory/api/main.py` — gate do startup/shutdown hook por env.

### Arquivos Dependentes
- `openmemory/api/app/utils/write_queue.py` — fila compartilhada entre API e worker.
- `openmemory/docker-compose.yml` — base para o serviço de worker no stack.

### ADRs Relacionados
- [ADR-003: Fila durável em PostgreSQL com FOR UPDATE SKIP LOCKED e workers em processo separado](../adrs/adr-003.md) — Define o worker como processo separado.

## Entregáveis
- Entrypoint de worker independente.
- Startup hook embutido gated por env.
- Encerramento gracioso.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração API+worker compartilhando fila **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Entrypoint inicia o `WriteWorker.run()` e responde a sinal de stop encerrando a task.
  - [ ] Com `RUN_EMBEDDED_WORKER` desabilitado, a API NÃO inicia o worker embutido.
  - [ ] Com a flag habilitada, a API inicia o worker embutido (modo dev).
- Testes de integração:
  - [ ] Job enfileirado pela API é processado por um worker em processo separado apontando ao mesmo banco.
  - [ ] Encerramento gracioso não deixa jobs perdidos (voltam a `queued`/`processing` consistente).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Worker escala por réplicas independentemente da API.
- Comportamento dev (worker embutido) preservado via flag.
