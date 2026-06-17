---
status: completed
title: Endpoint `GET /discovery` (JSON de config MCP)
type: backend
complexity: low
dependencies:
  - task_07
---

# Endpoint `GET /discovery` (JSON de config MCP)

## Visão Geral
Expor um endpoint HTTP de auto-descoberta que retorna a configuração MCP em JSON, permitindo que os agentes se autoconfigurem sem ajuste manual. O conteúdo descreve transporte, URL base e o template de rota com os campos a preencher (hostname e `project`).

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir um endpoint GET que retorna JSON com `transport`, `base_url`, `route_template` e `fields` (incluindo `user_id`=hostname e `project` obrigatório).
- O JSON DEVE refletir a configuração de runtime (host/porta e transportes habilitados).
- O contrato DEVE ser consistente com a rota MCP e os campos definidos nas tarefas 04 e 07.
- O endpoint DEVE responder 200 com JSON válido.
</requirements>

## Subtarefas
- [ ] 08.1 Criar o router/rota GET de descoberta no FastAPI.
- [ ] 08.2 Montar o JSON a partir da configuração de runtime (host/porta/transportes).
- [ ] 08.3 Incluir e registrar o router no app.
- [ ] 08.4 Cobrir com testes o formato e o conteúdo do JSON.

## Detalhes de Implementação
Adicionar um novo router em `openmemory/api/app/routers/` (padrão `APIRouter`) e incluí-lo em `openmemory/api/main.py` (junto aos demais `include_router`). O conteúdo do JSON segue "Endpoints de API → Recurso Descoberta" do TechSpec. O caminho exato (`/discovery` ou `/.well-known/mcp`) pode ser decidido na implementação (ver ADR-005).

### Arquivos Relevantes
- `openmemory/api/app/routers/discovery.py` (novo) — rota GET de descoberta.
- `openmemory/api/main.py` — registro do router.
- `openmemory/api/app/mcp_server.py` — referência do `route_template` e campos.

### Arquivos Dependentes
- Clientes/agentes MCP — consomem o JSON para autoconfiguração.

### ADRs Relacionados
- [ADR-005: Auto-descoberta de conexão MCP via endpoint JSON](../adrs/adr-005.md) — Conteúdo e formato do JSON.

## Entregáveis
- Endpoint GET de descoberta retornando o JSON de config MCP.
- Router registrado no app.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para a resposta do endpoint **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] GET de descoberta retorna 200 e JSON com `transport`, `base_url`, `route_template`, `fields`.
  - [ ] `fields` indica `user_id`=hostname e `project` como obrigatório.
  - [ ] `base_url`/transportes refletem a configuração de runtime.
- Testes de integração:
  - [ ] Cliente faz GET e obtém um JSON suficiente para montar a conexão MCP (campos presentes e coerentes com a rota real).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Agente obtém config MCP via GET sem configuração manual
- JSON coerente com a rota e os campos reais
