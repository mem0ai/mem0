---
status: pending
title: Reverse proxy + réplicas (rate limit, circuit breaker, sticky SSE, discovery)
type: infra
complexity: high
dependencies:
  - task_04
  - task_05
---

# Reverse proxy + réplicas (rate limit, circuit breaker, sticky SSE, discovery)

## Visão Geral
Coloca um reverse proxy (Traefik/Nginx) à frente das réplicas da API como camada de borda, com rate limiting, circuit breaker e afinidade de sessão para o MCP SSE. A auto-descoberta passa a anunciar a URL do proxy, preservando a instalação fácil do cliente e dos hooks.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir um reverse proxy balanceando N réplicas da API, com sticky sessions para as conexões MCP SSE.
- DEVE aplicar rate limiting por `project`+`hostname` (busca) e por `project` (escrita), com limites de burst por cliente.
- DEVE aplicar circuit breaker sob taxa de erro alta para os serviços de inferência/Qdrant.
- O endpoint de auto-descoberta (`/discovery`, `/.well-known/mcp`) DEVE anunciar a URL pública do proxy, configurável via env.
- O contrato MCP, o compat_v3 e o fluxo de install do cliente DEVEM permanecer inalterados.
</requirements>

## Subtarefas
- [ ] 6.1 Configurar o reverse proxy com LB das réplicas e sticky sessions para SSE.
- [ ] 6.2 Definir as regras de rate limiting por `project`/`hostname` e burst por cliente.
- [ ] 6.3 Configurar o circuit breaker para inferência/Qdrant.
- [ ] 6.4 Ajustar a auto-descoberta para anunciar a URL do proxy (via env).
- [ ] 6.5 Validar afinidade de sessão SSE e propagação de auth através do proxy.

## Detalhes de Implementação
Ver seções "Arquitetura do Sistema" (componente reverse proxy), "Endpoints de API" (preservação de discovery/hooks) e "Pontos de Integração" do TechSpec. A extração de `project`/`hostname` para o rate limit vem da rota/headers MCP. Limites sugeridos estão no ADR-004 (calibrar em carga).

### Arquivos Relevantes
- `openmemory/api/app/routers/discovery.py` — anunciar a URL do proxy (env).
- `openmemory/docker-compose.yml` — base para o serviço de proxy e réplicas da API.

### Arquivos Dependentes
- `openmemory/api/app/mcp_server.py` — transporte SSE/HTTP atrás do proxy (afinidade).
- `openmemory/api/app/routers/compat_v3.py` — hooks preservados atrás do proxy.

### ADRs Relacionados
- [ADR-004: Borda via reverse proxy (Traefik/Nginx) com rate limit, circuit breaker e sticky sessions SSE](../adrs/adr-004.md) — Define a camada de borda e a afinidade SSE.

## Entregáveis
- Reverse proxy com LB, sticky SSE, rate limit e circuit breaker.
- Discovery anunciando a URL do proxy.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de borda (rate limit + afinidade) **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `/discovery` retorna a URL do proxy quando a env de URL pública está definida.
  - [ ] `/discovery` reflete o host padrão quando a env não está definida (modo dev).
  - [ ] Contrato JSON de descoberta (transport, base_url, route_template) inalterado.
- Testes de integração:
  - [ ] Rajada acima do limite de busca por `project`+`hostname` recebe resposta de rate limit.
  - [ ] Sessão MCP SSE permanece na mesma réplica (afinidade) ao longo da sessão.
  - [ ] Escrita acima do limite por `project` é limitada; abaixo do limite passa.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Rajadas e loops de agentes não derrubam o serviço (borda protege).
- Cliente continua instalando/conectando via endpoint, agora pelo proxy.
