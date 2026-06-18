---
status: pending
title: Middleware de auth por equipe + Docker secrets (modo warn→enforce)
type: backend
complexity: high
dependencies:
  - task_10
---

# Tarefa 11: Middleware de auth por equipe + Docker secrets (modo warn→enforce)

## Visão Geral
Substitui o "trust-on-LAN" por autenticação proporcional ao risco: um token por equipe validado na borda e segredos movidos para Docker secrets, removendo valores sensíveis do `.env` versionado. Inclui modo de transição "warn" antes de tornar a validação obrigatória.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir um middleware que valide um token por equipe (header) contra um mapa `team→token` carregado de secret.
- DEVE haver dois modos: `warn` (loga/contabiliza ausência/invalidez sem bloquear) e `enforce` (rejeita 401), configurável por env.
- Segredos (tokens, credenciais MinIO/DB) DEVEM vir de Docker secrets ou arquivo montado fora do compose versionado; valores sensíveis DEVEM sair do `.env` versionado.
- DEVE manter a atribuição por hostname (`identity.py`) e o contrato MCP/compat_v3 intactos.
- A identidade da equipe DEVE ser registrada para auditoria.
</requirements>

## Subtarefas
- [ ] 11.1 Implementar o middleware de validação de token por equipe.
- [ ] 11.2 Carregar o mapa `team→token` de secret (não versionado).
- [ ] 11.3 Implementar os modos `warn` e `enforce` por env.
- [ ] 11.4 Migrar segredos para Docker secrets e limpar o `.env` versionado.
- [ ] 11.5 Registrar a equipe autenticada na auditoria existente.

## Detalhes de Implementação
Ver ADR-006 e seção "Arquitetura do Sistema" do TechSpec. Ordenar o middleware após o rate limit (task_10) e o `RequestIdMiddleware`. Reusar a auditoria de escrita existente para registrar a equipe.

### Arquivos Relevantes
- `openmemory/api/app/middleware/` — novo middleware de auth.
- `openmemory/api/app/routers/compat_v3.py` — hoje ignora o token; integrar sem quebrar contrato.
- `openmemory/api/app/utils/identity.py` — atribuição por hostname (mantida).
- `openmemory/api/main.py` — ordem de middlewares.
- `openmemory/docker-compose.scale.yml`, `openmemory/compose/*` — Docker secrets.

### Arquivos Dependentes
- `openmemory/api/tests/test_team_auth.py` (novo) — testes do middleware.

### ADRs Relacionados
- [ADR-006: Endurecimento para LAN — API key por equipe, secrets gerenciados e rate limit por project](adrs/adr-006.md) — define auth e secrets.

## Entregáveis
- Middleware de auth por equipe com modos warn/enforce.
- Segredos em Docker secrets; `.env` versionado sem valores sensíveis.
- Auditoria registrando a equipe.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Teste de integração dos modos warn e enforce **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Token válido em `enforce`: requisição passa e equipe é registrada.
  - [ ] Token inválido/ausente em `enforce`: retorna 401.
  - [ ] Token inválido/ausente em `warn`: passa, mas registra/contabiliza.
  - [ ] Contrato MCP/compat_v3 permanece funcional com token válido.
- Testes de integração:
  - [ ] Virada `warn`→`enforce` por env muda o comportamento sem alterar código.
  - [ ] Segredos carregados de secret montado (não do `.env`).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Nenhuma operação aceita sem credencial de equipe em `enforce`
- Zero segredo sensível em texto plano no repositório
