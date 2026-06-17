---
status: completed
title: Empacotamento docker-compose (Qdrant + Ollama + envs)
type: infra
complexity: medium
dependencies:
  - task_06
  - task_07
  - task_08
  - task_09
---

# Empacotamento docker-compose (Qdrant + Ollama + envs)

## Visão Geral
Empacotar a solução como uma instalação única na rede local via docker-compose, com Qdrant em container, acesso ao Ollama local e as variáveis de ambiente necessárias. Consolida o servidor MCP, a fila/worker, a descoberta e a detecção de modelos em um deploy reproduzível.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O docker-compose DEVE subir o servidor MCP/API e o Qdrant em container (porta 6333).
- A configuração DEVE permitir acesso ao Ollama local na rede (via `OLLAMA_BASE_URL`).
- As variáveis de ambiente DEVEM cobrir provider/modelos (selecionados na instalação), Qdrant e DB.
- O serviço DEVE expor a porta do MCP/API e ficar pronto para conexões de agentes na rede local.
- NÃO DEVE haver dependência de serviços fora da rede local (privacidade).
</requirements>

## Subtarefas
- [ ] 10.1 Ajustar o docker-compose com os serviços (API/MCP + Qdrant) e portas.
- [ ] 10.2 Configurar acesso ao Ollama local e as variáveis de ambiente.
- [ ] 10.3 Garantir persistência de dados (volumes) do Qdrant e do SQLite.
- [ ] 10.4 Documentar o passo de instalação (incluindo a detecção de modelos).
- [ ] 10.5 Validar a subida ponta a ponta (smoke) do conjunto.

## Detalhes de Implementação
Partir do `openmemory/docker-compose.yml` existente (serviços `mem0_store`/Qdrant, `openmemory-mcp`, `openmemory-ui`) e ajustar envs/volumes. Variáveis seguem `openmemory/api/.env.example` (`LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDER_PROVIDER`, `OLLAMA_BASE_URL`, `QDRANT_HOST`/`QDRANT_PORT`, `DATABASE_URL`). Ver "Pontos de Integração" e "Dependências Técnicas" do TechSpec.

### Arquivos Relevantes
- `openmemory/docker-compose.yml` — serviços, portas e volumes.
- `openmemory/api/.env.example` — chaves de configuração.

### Arquivos Dependentes
- Worker/fila (tarefa 06), `add_memories` (tarefa 07), descoberta (tarefa 08), detecção de modelos (tarefa 09) — todos precisam estar disponíveis no container.

### ADRs Relacionados
- [ADR-001: Evoluir o OpenMemory (MCP-first)](../adrs/adr-001.md) — Deploy reusando o docker-compose existente.
- [ADR-003: Qdrant em coleção única](../adrs/adr-003.md) — Qdrant em container.

## Entregáveis
- `docker-compose.yml` ajustado (API/MCP + Qdrant + envs + volumes).
- `.env.example` atualizado com as chaves necessárias.
- Documentação do passo de instalação.
- Testes/validações de subida (smoke) **(OBRIGATÓRIO)**
- Verificação de ausência de dependências externas à rede local **(OBRIGATÓRIO)**

## Testes
- Testes de integração/validação:
  - [ ] `docker compose up` sobe API/MCP e Qdrant; endpoint de descoberta responde 200.
  - [ ] O serviço conecta ao Ollama via `OLLAMA_BASE_URL` configurado.
  - [ ] Volume do Qdrant persiste memórias após reinício do container.
  - [ ] Smoke ponta a ponta: enfileirar via `add_memories` → worker processa → `search` recupera.
  - [ ] Nenhuma chamada de saída para fora da rede local é necessária para operar.
- Meta de cobertura: >= 80% (onde aplicável a código de suporte)
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Instalação única sobe o conjunto na rede local
- Memórias persistem entre reinícios; descoberta e fluxo escrita→leitura funcionam
- Operação 100% local, sem dependências externas
