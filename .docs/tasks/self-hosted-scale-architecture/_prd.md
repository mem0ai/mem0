# PRD — Arquitetura self-hosted em escala para Mem0/OpenMemory

> **Idioma:** PT-BR. **Status:** rascunho para revisão. **Data:** 2026-06-16.

## Visão Geral

A memória compartilhada Mem0/OpenMemory já é usada por equipes de desenvolvimento via agentes MCP (Cursor, Claude, Codex). O deploy atual — pensado para um time pequeno — não sustenta o uso planejado por **200 desenvolvedores** e dezenas de agentes simultâneos. O sintoma mais visível é a **lentidão da busca no início de cada sessão**: cada consulta faz o cálculo de embedding de forma inline em um serviço compartilhado antes de chegar ao mecanismo de busca, somando segundos de espera que quebram o fluxo de trabalho do dev.

Este produto entrega uma **arquitetura escalada self-hosted** que remove os dois maiores gargalos — embedding inline e escrita acoplada — para que os 200 devs tenham busca em tempo sub-segundo e o sistema permaneça estável sob pico, sem abrir mão da privacidade de manter tudo na infraestrutura da empresa.

- **Qual problema resolve:** a memória compartilhada fica lenta e instável quando muitos devs a usam ao mesmo tempo, atrapalhando a adoção.
- **Para quem é:** desenvolvedores que usam agentes de IA no dia a dia (consumidores) e a equipe de plataforma/infraestrutura que opera o serviço (operadores).
- **Por que é valioso:** transforma uma ferramenta que "trava sob carga" em um serviço confiável e rápido para toda a engenharia, viabilizando a adoção ampla já planejada.

## Objetivos

- **Desbloquear a adoção pelos 200 devs**: a capacidade e a latência deixam de ser barreira para o uso amplo.
- **Latência de leitura previsível sob carga**: busca rápida mesmo com muitos devs simultâneos (meta principal de qualidade percebida).
- **Estabilidade sob pico**: o serviço não cai nem perde memórias quando o uso concentra.
- **Métrica de sucesso combinada (p99 + adoção)**: atingir as metas de latência p99 **e** sustentar adoção ativa crescente sem incidentes de performance.
- **Marco-alvo**: entrega do MVP (Fases 0+1) em um único ciclo coordenado, com o caminho de leitura priorizado e validado primeiro (ver [ADR-001](adrs/adr-001.md)).

## Histórias de Usuário

### Persona principal — Desenvolvedor (consumidor via agente MCP)

- Como **dev usando o agente**, quero que a busca de memória no início da sessão retorne em sub-segundo, para que o agente já chegue contextualizado sem me fazer esperar.
- Como **dev**, quero que o que aprendi/registrei apareça nas buscas seguintes em tempo razoável, para que a memória compartilhada seja confiável.
- Como **dev**, quero que o sistema continue respondendo mesmo quando muitos colegas estão usando ao mesmo tempo, para que minha sessão não falhe em horário de pico.

### Persona secundária — Equipe de plataforma (operador)

- Como **operador**, quero escalar a capacidade de leitura e de escrita de forma independente, para acompanhar o crescimento da adoção sem reescrever o sistema.
- Como **operador**, quero visibilidade sobre latência, profundidade de fila e taxa de erro, para detectar degradação antes que os devs reclamem.
- Como **operador**, quero proteção de borda contra rajadas de requisições, para que um agente em loop não derrube o serviço para todos.

### Casos de borda

- Pico simultâneo de várias sessões disparando context-loader ao mesmo tempo.
- Agente repetindo buscas quase idênticas em curto intervalo.
- Falha transitória de um componente de leitura ou escrita sem perda de memórias enfileiradas.

## Funcionalidades Principais

Agrupadas por prioridade dentro do MVP (Fases 0+1).

### P0 — Caminho de leitura rápido

- **Serviço de embedding dedicado**: o cálculo de embedding deixa de competir com a extração e deixa de ser inline; passa a ser um serviço próprio que pode escalar conforme a demanda. _Por quê:_ é o gargalo #1 da latência percebida.
- **Cache de embedding e de resultados de busca**: consultas repetidas ou semelhantes reaproveitam trabalho já feito, devolvendo resultados quase instantâneos. _Por quê:_ agentes repetem muitas queries; alto retorno sobre a latência.
- **Capacidade de leitura escalável**: a camada que atende as buscas pode ter múltiplas réplicas atrás de um ponto de entrada único. _Por quê:_ suporta a concorrência dos 200 devs.

### P0 — Proteção de borda

- **Rate limiting e circuit breaker**: limites por projeto/cliente para buscas e escritas, com corte automático quando um componente degrada. _Por quê:_ impede que rajadas (ex.: agente em loop) derrubem o serviço para todos.

### P0 — Fundação durável de escrita

- **Fila de escrita durável e workers desacoplados**: o registro de memórias passa a usar uma fila persistente e um conjunto de workers que escala independentemente, com confirmação imediata ao agente e reprocessamento em caso de falha. _Por quê:_ remove o limite rígido de concorrência atual e garante que nenhuma memória se perca.
- **Metadados em armazenamento compartilhado robusto**: o catálogo, o histórico e a auditoria deixam o arquivo local único e passam a um banco compartilhado adequado a muitas conexões simultâneas. _Por quê:_ evita que o gargalo de leitura apenas se desloque para a escrita/conexões.

### Interação entre funcionalidades

O caminho de leitura (embedding dedicado + cache + réplicas) entrega o ganho de latência percebido; a fundação durável de escrita garante que esse ganho não exponha um novo gargalo. A proteção de borda preserva a estabilidade de ambos sob pico. O contrato dos agentes MCP (`search_memory`, `add_memories`) permanece inalterado.

## Experiência do Usuário

### Dev (consumidor)

1. Abre o agente no IDE; a sessão inicia e o context-loader dispara a busca de memória.
2. A busca retorna em sub-segundo (cache quente) ou em frações de segundo (cache frio), sem a pausa atual.
3. Ao longo do trabalho, o agente registra aprendizados; a confirmação é imediata e o conteúdo aparece nas buscas seguintes em tempo razoável.
4. Em horário de pico, a experiência permanece consistente — sem erros nem travamentos.

> A experiência do dev **não muda visualmente**: as mesmas ferramentas MCP, agora rápidas e estáveis. O onboarding do dev permanece o mesmo (autodescoberta/provisionamento já existentes).

### Operador (plataforma)

1. Implanta os serviços no ambiente Docker Swarm / VMs.
2. Acompanha um painel com latência p99, profundidade de fila, taxa de cache e erros.
3. Ajusta o número de réplicas de leitura e de workers de escrita conforme a adoção cresce.

### Acessibilidade

Sem mudança de interface para o dev; o produto é de infraestrutura. As metas de acessibilidade da UI existente permanecem inalteradas.

## Restrições Técnicas de Alto Nível

- **Self-hosted obrigatório**: todos os dados de memória permanecem na infraestrutura da empresa; nenhum dado sai para serviços externos. Mantém a privacidade como requisito não negociável.
- **Ambiente de deploy**: Docker Swarm / VMs dedicadas (sem Kubernetes). Escalonamento de réplicas e workers é manual neste MVP; não há autoscaling automático.
- **Compatibilidade de contrato**: os agentes MCP existentes continuam funcionando sem alteração de configuração.
- **Metas de desempenho na perspectiva do usuário**:
  - Busca (cache quente): p99 < 100 ms.
  - Busca (cache frio): p99 < 300 ms.
  - Confirmação de escrita ao agente: < 50 ms.
  - Processamento de escrita (p95 da fila): < 60 s.
- **Privacidade/segurança**: a comunicação e o acesso seguem o modelo atual de confiança na rede interna; reforço de autenticação por equipe e RBAC ficam como pergunta em aberto / fase futura.

## Fora de Escopo (Non-Goals)

- **Particionamento do Qdrant** (coleções por projeto, cluster, sharding, índices por coleção) — Fase 2, fora do MVP.
- **Governança de memória** (consolidação/dream, TTL/pruning, cold tier para projetos inativos) — Fase 3.
- **Autoscaling automático (HPA)** — depende de Kubernetes, fora do ambiente escolhido.
- **RBAC, mTLS e isolamento multi-tenant por equipe** — postura enterprise/compliance não é o objetivo deste MVP.
- **Busca híbrida (semântica + keyword + entidade) no caminho crítico do MCP** — opcional em fase futura.
- **Migração de qualidade/precisão de memória** (re-ranking avançado, grafo temporal) — não é objetivo aqui.

## Plano de Entrega por Fases

### MVP (Fase 1 deste PRD = Fases 0+1 da proposta técnica)

Entrega integrada e coesa, com o caminho de leitura priorizado no rollout interno ([ADR-001](adrs/adr-001.md)):

- Caminho de leitura rápido: embedding dedicado + cache + capacidade de leitura escalável.
- Proteção de borda: rate limiting + circuit breaker.
- Fundação durável de escrita: fila durável + workers desacoplados + metadados em banco compartilhado.
- Observabilidade básica: painel de latência p99, profundidade de fila, taxa de cache e erros.

**Critérios de sucesso para avançar:**
- Busca p99 dentro das metas (< 100 ms quente / < 300 ms frio) sob carga representativa dos 200 devs.
- Zero perda de escrita; lag de processamento p95 < 60 s.
- Adoção ativa crescente sem incidentes de performance reportados.

### Fase 2 — Particionamento e escala de armazenamento

- Coleções por projeto e índices de payload adequados; cluster do mecanismo de busca.
- Critério para avançar: nenhum projeto individual próximo do limite de volume degradando a busca.

### Fase 3 — Governança e elasticidade contínua

- Consolidação (dream), TTL/pruning, cold tier; autoscaling se houver migração para orquestrador elástico.
- Critério de longo prazo: qualidade de memória estável e custo de operação sob controle com centenas de milhões de memórias.

## Métricas de Sucesso

- **Latência de busca p99** (principal qualidade percebida): < 100 ms (cache quente), < 300 ms (cache frio), sustentada sob carga dos 200 devs.
- **Adoção ativa**: número de devs/agentes usando ativamente por semana, em crescimento, sem reclamações de performance.
- **Durabilidade da escrita**: zero memórias perdidas; lag de fila p95 < 60 s.
- **Estabilidade**: ausência de incidentes de indisponibilidade em horário de pico.
- **Eficiência de cache**: taxa de acerto do cache de embedding acima de um patamar saudável (sinal de que a otimização de leitura está rendendo).

## Riscos e Mitigações

- **Risco de adoção — expectativa não atendida**: se a latência não melhorar de forma perceptível no primeiro contato, os devs podem abandonar a ferramenta. _Mitigação:_ priorizar o caminho de leitura no rollout para entregar o ganho cedo (ADR-001).
- **Risco de cronograma — escopo coordenado**: entregar fundação e leitura no mesmo ciclo amplia a superfície de validação. _Mitigação:_ rollout interno faseado dentro do MVP (validar fundação antes de redirecionar o tráfego de leitura).
- **Risco operacional — equipe de plataforma**: operar mais serviços em Swarm/VMs exige capacidade da equipe de infraestrutura. _Mitigação:_ observabilidade desde o início e escalonamento manual documentado.
- **Risco de dependência externa — capacidade de hardware**: o ganho de embedding pode depender de recursos (ex.: GPU) ainda não provisionados. _Mitigação:_ registrar como pergunta em aberto e validar disponibilidade antes da implementação.
- **Risco competitivo**: soluções gerenciadas (Mem0 Platform) e concorrentes (Zep, Letta) oferecem escala "pronta". _Mitigação:_ o diferencial é a privacidade self-hosted total — manter esse valor central na comunicação.

## Registros de Decisão de Arquitetura

- [ADR-001: Entrega integrada das Fases 0+1 com caminho de leitura priorizado](adrs/adr-001.md) — Tratar Fases 0+1 como MVP único, priorizando o caminho de leitura no rollout para entregar a redução de latência cedo sem deslocar o gargalo para a escrita.

## Perguntas em Aberto

- **Capacidade de hardware**: há GPU/recursos disponíveis na infraestrutura para o serviço de embedding dedicado, ou será necessário cluster de CPU? (impacta as metas de throughput)
- **Autenticação e RBAC**: o modelo atual de "confiança na rede interna" é aceitável para 200 devs, ou o MVP deve incluir ao menos chave de API por equipe? (definido como fora de escopo, mas a confirmar com stakeholders)
- **Carga representativa**: quais números reais de QPS de busca e taxa de escrita devem ser usados como alvo de teste de carga? (os valores da proposta são ordem de grandeza)
- **Janela de migração**: qual a janela aceitável para migrar os metadados do armazenamento local atual para o banco compartilhado sem interromper o uso?
- **Responsável pela operação**: qual equipe assume a operação contínua (escalonamento manual, resposta a alertas) no ambiente Swarm/VMs?
