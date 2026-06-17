---
status: pending
title: Serviços de inferência dedicados (Ollama/llama.cpp) + config do cliente mem0
type: infra
complexity: medium
dependencies: []
---

# Serviços de inferência dedicados (Ollama/llama.cpp) + config do cliente mem0

## Visão Geral
Remove a inferência inline do host, criando dois serviços dedicados e replicáveis — embedding e LLM de extração — acessados por endpoint próprio. O cliente mem0 passa a apontar para esses endpoints via configuração explícita, suportando tanto Ollama quanto llama.cpp sem novo código de provider.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVEM existir dois serviços de inferência dedicados e replicáveis: embedding e LLM, em recursos separados (sem contenção entre si).
- O cliente mem0 DEVE consumir esses serviços via configuração explícita de provider + `base_url`, sem alterar o código dos providers do mem0.
- DEVE suportar Ollama (provider `ollama`) e llama.cpp (provider `openai` com `openai_base_url` apontando ao `llama-server`).
- Quando o endpoint explícito estiver configurado, ele DEVE ter precedência sobre a resolução `localhost`→`host.docker.internal` (modo dev preservado quando não houver endpoint explícito).
- O guard local-only DEVE continuar válido com `base_url` privada.
</requirements>

## Subtarefas
- [ ] 4.1 Definir os serviços dedicados de embedding e LLM (replicáveis, recursos separados) no stack.
- [ ] 4.2 Mapear env → config do cliente mem0 para apontar provider/`base_url` aos serviços dedicados.
- [ ] 4.3 Garantir suporte a Ollama e llama.cpp (OpenAI-compatible) por configuração.
- [ ] 4.4 Assegurar precedência do endpoint explícito sobre a auto-resolução de host.
- [ ] 4.5 Validar o guard local-only com endpoints privados.

## Detalhes de Implementação
Ver seção "Interfaces Principais" (config do cliente mem0) e "Pontos de Integração" do TechSpec. A camada de embedder/LLM do mem0 já resolve provider por config (`EmbedderFactory`/`LlmFactory`); llama.cpp pluga pelo provider `openai` via `openai_base_url`. Esta tarefa cobre apenas os serviços dedicados e o consumo da config explícita; a DETECÇÃO automática no install fica na task_08.

### Arquivos Relevantes
- `openmemory/api/app/utils/memory.py` — montagem da config (env → provider/`base_url`); precedência do endpoint explícito.
- `openmemory/docker-compose.yml` — base para os serviços dedicados de inferência.

### Arquivos Dependentes
- `mem0/utils/factory.py` — `EmbedderFactory`/`LlmFactory` (consumidos, não alterados).
- `mem0/embeddings/openai.py`, `mem0/embeddings/ollama.py` — providers usados por config.

### ADRs Relacionados
- [ADR-002: Embedding e LLM como serviços Ollama/llama.cpp dedicados via base_url](../adrs/adr-002.md) — Define os serviços dedicados, o modo duplo e o suporte multi-backend.

## Entregáveis
- Dois serviços de inferência dedicados (embedding e LLM) no stack.
- Config do cliente mem0 consumindo endpoints explícitos (Ollama e llama.cpp).
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de conectividade com os serviços **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Env apontando para serviço dedicado gera config com provider/`base_url` corretos (Ollama).
  - [ ] Env de llama.cpp gera config provider `openai` + `openai_base_url`.
  - [ ] Endpoint explícito tem precedência sobre `localhost`→`host.docker.internal`.
  - [ ] Guard local-only aceita `base_url` privada e rejeita endpoint não-local.
- Testes de integração:
  - [ ] Cliente mem0 inicializa e executa um embedding contra o serviço dedicado (stub/container).
  - [ ] Extração via serviço LLM dedicado retorna resultado válido (stub/container).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Embedding e extração rodam em serviços dedicados, escaláveis por réplica.
- Troca entre Ollama e llama.cpp feita só por configuração.
