---
status: completed
title: Detecção de modelos na instalação (Ollama `/api/tags`)
type: infra
complexity: medium
dependencies:
  - task_01
---

# Detecção de modelos na instalação (Ollama `/api/tags`)

## Visão Geral
Adicionar um passo de instalação que consulta o Ollama (`/api/tags`) para detectar os modelos locais disponíveis e os lista para o admin escolher LLM e embedder, eliminando a digitação manual. Inclui fallback para entrada manual caso o Ollama esteja indisponível.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O setup DEVE consultar o Ollama (`/api/tags`) e listar os modelos instalados.
- O admin DEVE poder selecionar qual modelo usar como LLM e qual como embedder.
- A seleção DEVE alimentar a configuração de runtime do mem0 (providers `ollama`).
- DEVE haver fallback para entrada manual do nome do modelo se a consulta falhar.
- NÃO DEVE realizar auto-seleção nem download automático (fora de escopo do MVP).
</requirements>

## Subtarefas
- [ ] 09.1 Consultar a lista de modelos do Ollama e parsear o resultado.
- [ ] 09.2 Apresentar os modelos para seleção de LLM e embedder.
- [ ] 09.3 Persistir a seleção na configuração de runtime do mem0.
- [ ] 09.4 Implementar fallback para entrada manual em caso de falha.
- [ ] 09.5 Cobrir com testes a detecção, a seleção e o fallback.

## Detalhes de Implementação
Reusar o cliente Ollama já presente — `client.list()` é usado em `mem0/embeddings/ollama.py` (`_ensure_model_exists`) e retorna `{"models": [...]}`. A seleção alimenta os factories de config em `openmemory/api/app/utils/memory.py` (providers `ollama`). Ver "Arquitetura → Detecção de Modelos na Instalação" e "Endpoints de API → Recurso Setup/Modelos" do TechSpec.

### Arquivos Relevantes
- `openmemory/api/app/utils/memory.py` — factories de config de LLM/embedder Ollama.
- `mem0/embeddings/ollama.py` / `mem0/llms/ollama.py` — uso de `client.list()` e `ollama_base_url`.

### Arquivos Dependentes
- Núcleo mem0 (tarefa 01) — usa a config resultante via `Memory.from_config`.
- Empacotamento (tarefa 10) — integra o passo de setup ao fluxo de instalação.

### ADRs Relacionados
- [ADR-006: Detecção de LLMs/embedders locais na instalação via Ollama](../adrs/adr-006.md) — Detectar e listar para o admin escolher.

## Entregáveis
- Passo de setup que detecta e lista modelos do Ollama para seleção.
- Seleção persistida na config de runtime; fallback manual.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para detecção/seleção com Ollama mockado **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `client.list()` mockado retornando 2 modelos resulta em lista apresentável com os 2 nomes.
  - [ ] Seleção de LLM e embedder grava os providers `ollama` com os modelos escolhidos na config.
  - [ ] Ollama indisponível (exceção em `list()`) aciona o fallback de entrada manual.
  - [ ] Nenhum download (`pull`) é disparado pelo passo de detecção.
- Testes de integração:
  - [ ] Fluxo de setup produz uma config válida consumível por `Memory.from_config`.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Modelos locais detectados e selecionáveis no setup
- Fallback manual funcional quando o Ollama está indisponível
