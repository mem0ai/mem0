---
status: pending
title: Middleware de rate limit por project+hostname (Redis sliding-window)
type: backend
complexity: medium
dependencies:
  - task_01
---

# Tarefa 10: Middleware de rate limit por project+hostname (Redis sliding-window)

## Visão Geral
Substitui o rate limit global do Traefik por limites granulares por `(project, hostname)`, usando uma janela deslizante no Redis já existente, conforme §1 da arquitetura. Protege contra rajadas de um único consumidor sem penalizar os demais.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir um middleware que limite busca e escrita por `(project, hostname)` com janela deslizante no Redis.
- Os limites DEVEM ser configuráveis por env, com defaults da §1 (busca 30/min, escrita 60/min, burst 10/10s).
- Ao exceder, DEVE retornar 429 com cabeçalho indicando retry.
- O middleware NÃO PODE quebrar o contrato MCP nem o compat_v3.
- Falha do Redis DEVE degradar com segurança (fail-open configurável) sem derrubar requisições.
</requirements>

## Subtarefas
- [ ] 10.1 Implementar a contagem por janela deslizante no Redis.
- [ ] 10.2 Aplicar o middleware às rotas de busca e escrita, extraindo `project`/`hostname`.
- [ ] 10.3 Tornar limites configuráveis por env com os defaults da §1.
- [ ] 10.4 Retornar 429 com `Retry-After` ao exceder.
- [ ] 10.5 Definir comportamento em falha do Redis (fail-open/closed configurável).

## Detalhes de Implementação
Ver ADR-006 e seção "Arquitetura do Sistema" do TechSpec. Reusar a conexão Redis do `app/utils/read_cache.py`. Ordenar o middleware após `RequestIdMiddleware`. `project`/`hostname` derivam do contexto já existente (`identity.py`, vars de contexto do MCP).

### Arquivos Relevantes
- `openmemory/api/app/middleware/` — novo middleware de rate limit.
- `openmemory/api/app/utils/read_cache.py` — conexão Redis reusável.
- `openmemory/api/app/utils/identity.py` — resolução de hostname.
- `openmemory/api/main.py` — registro/ordem dos middlewares.
- `openmemory/compose/proxy.yml` — remover/ajustar o limite global do Traefik para essas rotas.

### Arquivos Dependentes
- `openmemory/api/tests/test_rate_limit.py` (novo) — testes.

### ADRs Relacionados
- [ADR-006: Endurecimento para LAN — API key por equipe, secrets gerenciados e rate limit por project](adrs/adr-006.md) — define rate limit por project.

## Entregáveis
- Middleware de rate limit por `(project, hostname)` ativo.
- Limites configuráveis e 429 com `Retry-After`.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Teste de integração de estouro e liberação de janela **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Dentro do limite: requisições passam.
  - [ ] Acima do limite de busca (30/min): retorna 429 com `Retry-After`.
  - [ ] Limites independentes por `(project, hostname)` distintos.
  - [ ] Falha do Redis em modo fail-open não bloqueia requisições.
- Testes de integração:
  - [ ] Estourar a janela e, após expirar, voltar a aceitar requisições.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Limite aplicado por project+hostname, não global
