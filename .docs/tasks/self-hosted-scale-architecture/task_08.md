---
status: pending
title: Stack único + bootstrap automatizado (detecção multi-backend + migração)
type: infra
complexity: critical
dependencies:
  - task_01
  - task_02
  - task_03
  - task_04
  - task_05
  - task_06
  - task_07
---

# Stack único + bootstrap automatizado (detecção multi-backend + migração)

## Visão Geral
Empacota todos os componentes em um stack único (Swarm + instruções VMs) que sobe com um comando, mais um bootstrap script idempotente que provisiona banco, roda migrations, cria índices, detecta o backend de inferência (Ollama/llama.cpp) e aplica a configuração por template. Preserva o requisito de instalação simplificada apesar do número de serviços.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir um arquivo de stack (Swarm) que sobe todos os serviços com um comando, com healthchecks e ordem de dependência entre serviços.
- O bootstrap script DEVE ser idempotente e: provisionar o PostgreSQL, rodar `alembic upgrade head`, criar/garantir os índices de payload no Qdrant e aplicar config via template de env.
- O bootstrap DEVE detectar o backend de inferência no modo dev/single-host — Ollama via `/api/tags` e llama.cpp via `llama-server` (OpenAI-compatible) — e gravar o provider/`base_url` correspondente; em produção, usar os endpoints explícitos com precedência.
- A subida DEVE validar `/health` dos componentes antes de liberar a borda.
- DEVE existir um caminho guiado de migração de dados SQLite→PostgreSQL (não 100% automático no MVP).
</requirements>

## Subtarefas
- [ ] 8.1 Escrever o arquivo de stack Swarm (e instruções equivalentes para VMs) com healthchecks e dependências.
- [ ] 8.2 Implementar o bootstrap script idempotente (provisão DB, migrations, índices Qdrant, config por template).
- [ ] 8.3 Implementar a detecção multi-backend no install (Ollama `/api/tags` e llama.cpp `llama-server`).
- [ ] 8.4 Adicionar o gate de `/health` antes de liberar a borda na subida.
- [ ] 8.5 Documentar e roteirizar a migração guiada SQLite→PostgreSQL.

## Detalhes de Implementação
Ver seções "Sequenciamento de Desenvolvimento" (passo 8), "Arquitetura do Sistema" (componente stack/bootstrap) e "Pontos de Integração" do TechSpec. Reusar/expandir o fluxo de provisionamento e `/discovery` existentes. As migrations já são driver-agnostic (task_01); o bootstrap apenas as dispara.

### Arquivos Relevantes
- `openmemory/docker-compose.yml` / arquivo de stack Swarm — orquestração de todos os serviços.
- `openmemory/api/` (script de bootstrap) — provisão, migrations, índices, config por template.
- `openmemory/api/app/utils/memory.py` — gravação do provider/`base_url` detectado.

### Arquivos Dependentes
- `openmemory/api/alembic/` — `alembic upgrade head` disparado pelo bootstrap.
- `mem0/vector_stores/qdrant.py` — criação/garantia dos índices de payload.
- `openmemory/api/app/routers/discovery.py` — provisionamento/anúncio do endpoint.

### ADRs Relacionados
- [ADR-006: Instalação automatizada via stack único + bootstrap script](../adrs/adr-006.md) — Define o stack e o bootstrap idempotente.
- [ADR-002: Embedding e LLM dedicados (Ollama/llama.cpp), detecção multi-backend](../adrs/adr-002.md) — Detecção no install e modo duplo.
- [ADR-003: Fila PostgreSQL + workers separados](../adrs/adr-003.md) — Migração de dados e migrations.

## Entregáveis
- Stack único (Swarm) + instruções VMs.
- Bootstrap script idempotente com detecção multi-backend.
- Roteiro de migração SQLite→PostgreSQL.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração da subida ponta a ponta **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Detecção retorna Ollama quando `/api/tags` responde com modelos.
  - [ ] Detecção retorna llama.cpp quando `llama-server` (`/v1/models`) responde.
  - [ ] Em produção, endpoint explícito tem precedência e a detecção não é executada.
  - [ ] Bootstrap é idempotente: segunda execução não duplica recursos nem falha.
- Testes de integração:
  - [ ] Subida do stack provisiona DB, roda migrations e cria índices Qdrant com sucesso.
  - [ ] Gate de `/health` impede liberar a borda até os componentes estarem saudáveis.
  - [ ] Migração guiada move `write_queue`/`projects`/`write_audit_logs` de SQLite para PostgreSQL sem perda.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Stack completo sobe com um comando + bootstrap, sem passos manuais espalhados.
- Backend de inferência detectado/configurado automaticamente no modo dev e explícito em produção.
