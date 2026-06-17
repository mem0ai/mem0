---
status: completed
title: Identidade por hostname no slot `user_id` (atribuição)
type: backend
complexity: low
dependencies:
  - task_03
---

# Identidade por hostname no slot `user_id` (atribuição)

## Visão Geral
Usar o nome da máquina (hostname) no segmento `user_id` da rota MCP apenas como identidade leve para atribuição e auditoria, sem cadastro/login. Como a busca já ignora `user_id` (tarefa 03), o hostname não restringe acesso — apenas rotula quem originou cada operação.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O valor recebido no segmento `user_id` da rota MCP DEVE ser tratado como hostname (identidade de atribuição).
- O hostname DEVE ser persistido como atribuição na escrita e registrado na auditoria.
- A identidade NÃO DEVE ser usada como filtro de leitura.
- Hostname ausente/vazio DEVE ter tratamento previsível (valor padrão claro), conforme pergunta em aberto do PRD.
</requirements>

## Subtarefas
- [ ] 04.1 Garantir captura do hostname a partir do segmento `user_id` da rota MCP (context var existente).
- [ ] 04.2 Propagar o hostname como atribuição na escrita (metadata) e na auditoria.
- [ ] 04.3 Definir tratamento para hostname ausente/genérico.
- [ ] 04.4 Cobrir com testes a atribuição por hostname e a não restrição na leitura.

## Detalhes de Implementação
Reusar `user_id_var`/`client_name_var` e o parsing de `request.path_params` já presentes em `openmemory/api/app/mcp_server.py` (registro de rota SSE ≈ linha 435). O hostname segue para o metadata da escrita (consumido na tarefa 07/06) e para o log de acesso. Ver "Decisões-Chave → Hostname como identidade" do TechSpec.

### Arquivos Relevantes
- `openmemory/api/app/mcp_server.py` — captura/propagação do hostname (slot `user_id`).
- `openmemory/api/app/models.py` — `MemoryAccessLog` para auditoria por hostname.

### Arquivos Dependentes
- Tarefa 07 — usa o hostname ao enfileirar a escrita.
- Tarefa 06 — persiste o hostname como atribuição na gravação.

### ADRs Relacionados
- [ADR-003: Identidade por hostname para atribuição](../adrs/adr-003.md) — Hostname no slot `user_id`, não usado como gate.

## Entregáveis
- Hostname capturado e propagado como atribuição/auditoria.
- Tratamento definido para hostname ausente/genérico.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para atribuição por hostname **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Requisição com `user_id`=`maqA` resulta em atribuição `hostname=maqA` na escrita.
  - [ ] Hostname ausente recebe o valor padrão definido (sem exceção).
  - [ ] A identidade não é adicionada como filtro de leitura.
- Testes de integração:
  - [ ] Operação registrada na auditoria com o hostname correto.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Atribuição por hostname registrada sem cadastro/login
- Identidade não restringe leitura compartilhada
