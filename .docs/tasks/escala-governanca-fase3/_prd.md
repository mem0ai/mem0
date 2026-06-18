# PRD — Fase 3: Governança de qualidade da memória

> **Idioma:** PT-BR. **Status:** rascunho para revisão. **Data:** 2026-06-18.
> **Predecessores:** [PRD da Fase 0+1](../self-hosted-scale-architecture/_prd.md) (leitura rápida + fundação durável) e [PRD da Fase 2](../particionamento-qdrant-fase2/_prd.md) (particionamento + cluster → latência plana).

## Visão Geral

A Fase 1 entregou busca de memória em tempo sub-segundo; a Fase 2 garantiu que essa latência **não regrida com o crescimento** do volume. Resolvido o problema de **velocidade**, emerge o próximo limite: a **qualidade da recuperação**. À medida que centenas de milhões de memórias se acumulam, o agente passa a receber resultados **duplicados, contraditórios e obsoletos** — a memória continua rápida, mas fica "suja". Isso corrói exatamente o que a torna útil: a confiança de que o que ela devolve é o conhecimento certo e atual.

Esta fase entrega a **governança de qualidade da memória**: jobs automáticos que **mantêm a base limpa** ao longo do tempo, mesclando duplicatas, resolvendo contradições e podando memórias obsoletas — sem que o desenvolvedor precise fazer nada e sem risco de perda acidental de conhecimento. A governança é **automática com rede de segurança** (ver [ADR-001](adrs/adr-001.md)): age sozinha por padrão, mas toda ação destrutiva é **reversível** (quarentena por um período antes do expurgo definitivo) e memórias marcadas como protegidas ("pinadas") nunca são tocadas.

A entrega é **faseada para reduzir risco**: primeiro os "guarda-corpos" de baixo risco (dedup reforçado + poda por tempo/uso), depois a consolidação semântica (merge de quase-duplicatas e resolução de contradições), que é mais valiosa para a qualidade, porém mais sensível.

- **Qual problema resolve:** o acúmulo de memórias duplicadas, contraditórias e obsoletas degrada a **qualidade** da recuperação, retornando lixo ao agente e minando a confiança na memória compartilhada.
- **Para quem é:** desenvolvedores que consomem a memória via agentes MCP (consumidores) e a equipe de plataforma que opera o serviço (operadores).
- **Por que é valioso:** preserva a **utilidade** da memória em escala — o agente recebe conhecimento limpo, atual e não-conflitante — mantendo a privacidade self-hosted e sem qualquer mudança para o dev.

## Objetivos

- **Qualidade da recuperação (objetivo principal):** reduzir de forma mensurável a fração de resultados duplicados, contraditórios e obsoletos retornados ao agente, sem perda de conhecimento legítimo.
- **Volume sob controle (objetivo de suporte):** estabilizar o crescimento líquido da base — poda e dedup compensam parte do ingresso — mantendo capacidade e latência previsíveis ao longo do tempo.
- **Segurança da automação:** nenhuma memória legítima é perdida de forma irreversível; toda ação destrutiva é reversível por um período e memórias pinadas são preservadas.
- **Operação sem fricção:** governança roda automaticamente, fora de pico, sem aprovação manual item a item e sem impacto perceptível para o dev.
- **Marco-alvo:** governança ativa por padrão sobre toda a base (com padrões conservadores), com o incremento de guarda-corpos validado em produção antes de ativar a consolidação semântica.

## Histórias de Usuário

### Persona principal — Desenvolvedor (consumidor via agente MCP)

- Como **dev**, quero que a busca devolva o conhecimento **certo e atual**, sem versões duplicadas ou contraditórias do mesmo fato, para confiar no que a memória me dá.
- Como **dev**, quero que informação obsoleta deixe de aparecer com o tempo, para não ser induzido por decisões/convenções que já não valem.
- Como **dev**, quero que conhecimento que marquei como importante **nunca** seja apagado, para não perder o que é crítico.
- Como **dev**, quero não perceber a governança acontecendo, para que meu fluxo de trabalho não mude.

### Persona secundária — Equipe de plataforma (operador)

- Como **operador**, quero que a base se mantenha limpa automaticamente, sem revisar duplicata por duplicata, para que a qualidade escale sem trabalho manual proporcional ao volume.
- Como **operador**, quero ver o que foi mesclado, podado ou colocado em quarentena e poder **reverter**, para operar a automação com segurança.
- Como **operador**, quero definir uma política padrão e ajustá-la para projetos específicos, para acomodar projetos com necessidades de retenção diferentes.
- Como **operador**, quero ativar a consolidação semântica só depois de confiar nos guarda-corpos, para introduzir a parte mais arriscada com segurança.

### Casos de borda

- Duas memórias dizem o oposto uma da outra (contradição) — qual prevalece e o que acontece com a perdedora.
- Memória antiga, mas ainda consultada com frequência — não deve ser podada só pela idade.
- Memória pinada que também é duplicata/obsoleta — a proteção prevalece sobre a poda/merge.
- Job de governança interrompido no meio (queda/reinício) — retoma sem efeitos parciais inconsistentes.
- Reversão de uma ação após o período de quarentena já ter expirado (expurgo definitivo) — limite do que é recuperável.
- Escrita de uma nova memória idêntica chegando enquanto o dedup roda.
- Projeto com política de retenção mais longa (ex.: decisões de arquitetura) convivendo com a política global.

## Funcionalidades Principais

Agrupadas por prioridade e por incremento dentro da Fase 3.

### P0 — Rede de segurança (transversal, habilita todo o resto)

- **Quarentena reversível (soft-delete):** toda ação destrutiva (poda, merge, resolução de contradição) primeiro **inativa** a memória por um período configurável antes do expurgo definitivo, permitindo reversão. _Por quê:_ é a condição para automatizar sem medo de perda de conhecimento.
- **Proteção de memórias pinadas:** memórias marcadas como protegidas (por categoria ou individualmente) **nunca** são mescladas, podadas ou movidas para quarentena. _Por quê:_ garante que conhecimento crítico seja imune à automação.
- **Trilha de auditoria + reversão (operador):** registro do que cada job fez (o quê, quando, por qual regra) com capacidade de reverter ações individuais ou em lote. _Por quê:_ controle humano sobre uma automação destrutiva.

### P0 — Incremento 1: Guarda-corpos de volume (baixo risco)

- **Dedup reforçado na escrita e em lote:** memórias idênticas/equivalentes por conteúdo deixam de ser duplicadas no ingresso e duplicatas exatas pré-existentes são consolidadas. _Por quê:_ elimina o tipo mais barato e seguro de ruído, controlando volume.
- **Poda por tempo e uso (TTL):** memórias antigas **e** sem acesso recente são podadas (para quarentena) segundo a política vigente, respeitando proteções. _Por quê:_ remove obsolescência que polui a recuperação e infla o volume; usar idade **e** último acesso evita apagar conhecimento antigo ainda relevante.

### P1 — Incremento 2: Consolidação semântica (maior valor, maior cuidado)

- **Merge de quase-duplicatas:** memórias que dizem essencialmente a mesma coisa (acima de um limiar de similaridade) são consolidadas numa única memória **canônica**, com as demais em quarentena. _Por quê:_ reduz redundância semântica que o dedup exato não pega — ganho direto de qualidade.
- **Resolução de contradições:** quando duas memórias se contradizem, a mais recente/confiável é mantida como canônica e a conflitante é colocada em quarentena. _Por quê:_ contradições são o pior tipo de ruído — fazem o agente confiar em informação errada.

### P1 — Governança configurável por projeto

- **Política global padrão:** um conjunto conservador (idade/uso para poda, agenda de consolidação, categorias protegidas) aplicado a toda a base. _Por quê:_ governança ativa por padrão sem configuração caso a caso.
- **Override por projeto:** o operador ajusta a política para projetos específicos (ex.: reter decisões de arquitetura por mais tempo). _Por quê:_ projetos têm perfis de retenção distintos; flexibilidade sem obrigar configuração de todos.

### Interação entre funcionalidades

A rede de segurança é a fundação: sem quarentena reversível e proteção de pinadas, nenhuma das ações destrutivas seria segura para automatizar. Sobre ela, o Incremento 1 controla volume com baixo risco e valida a automação em produção; o Incremento 2 adiciona o ganho de qualidade mais sensível (merge semântico e contradições) já com a rede de segurança comprovada. As políticas global+override modulam **com que intensidade** tudo isso roda por projeto. O contrato MCP (`search_memory`, `add_memories`) **permanece inalterado** — a governança é invisível ao dev.

## Experiência do Usuário

### Dev (consumidor)

1. Continua usando as mesmas ferramentas MCP no IDE, sem qualquer mudança de configuração ou de comportamento visível.
2. Com o tempo, percebe que as buscas devolvem resultados **mais limpos**: menos repetição, menos informação velha, menos contradição.
3. O conhecimento que marcou como importante permanece intacto.

> A experiência do dev **não muda visualmente**. O ganho é **qualidade crescente** da recuperação e a ausência de surpresas (nada importante desaparece).

### Operador (plataforma)

1. Define (ou aceita) a política global de governança e, opcionalmente, ajusta projetos específicos.
2. Ativa primeiro os guarda-corpos (dedup + TTL); acompanha pela trilha de auditoria o que está sendo podado/consolidado e o volume recuperado.
3. Ganha confiança na rede de segurança (revisando e, se preciso, revertendo ações) antes de ativar a consolidação semântica.
4. Após validação, ativa o merge semântico e a resolução de contradições, seguindo monitorando pela auditoria.

### Acessibilidade

Produto de infraestrutura; sem mudança de interface para o dev. Eventuais elementos novos no painel do operador (auditoria/reversão, edição de política) seguem os padrões da UI atual.

## Restrições Técnicas de Alto Nível

- **Self-hosted obrigatório:** todas as memórias e a governança permanecem na infraestrutura da empresa; nenhum dado sai para serviços externos.
- **Ambiente de deploy:** Docker Swarm / VMs dedicadas (sem Kubernetes). Jobs de governança rodam agendados/em background, operados manualmente; **sem autoscaling** (consistente com Fases 1 e 2).
- **Compatibilidade de contrato:** os agentes MCP (`search_memory`, `add_memories`) continuam funcionando sem alteração; a governança é transparente.
- **Reversibilidade obrigatória:** nenhuma ação destrutiva é definitiva de imediato; há janela de quarentena antes do expurgo e proteção de pinadas.
- **Continuidade de serviço:** jobs rodam fora de pico, sem downtime de leitura/escrita, e são retomáveis após falha sem efeitos parciais inconsistentes.
- **Metas de desempenho na perspectiva do usuário:** manter as metas das fases anteriores (busca p99 < 100 ms cache quente / < 300 ms cache frio; confirmação de escrita < 50 ms). A governança **não pode degradar** a latência percebida.
- **Privacidade/segurança:** mantém o modelo de confiança das fases anteriores; a auditoria registra ações de governança sem expor conteúdo sensível além do necessário.

## Fora de Escopo (Non-Goals)

- **Cold tier / arquivamento de projetos inativos** (snapshot externo + descarte de coleção) — adiado; esta fase trata de **qualidade**, não de mover projetos inteiros para armazenamento frio.
- **Busca híbrida (semântica + keyword + entidade) no caminho do MCP** — a capacidade técnica existe no core, mas sua ativação é uma iniciativa de **recall/relevância**, separada da governança; fora desta fase.
- **Autoscaling / HPA** — depende de orquestrador elástico, fora do ambiente escolhido (Swarm/VMs); permanece fora de escopo.
- **Governança sob aprovação manual item a item** — explicitamente descartada em favor de automação com rede de segurança ([ADR-001](adrs/adr-001.md)); não escala para o volume-alvo.
- **Transparência da governança ao dev** (sinais de "consolidada de N fontes" no resultado) — descartada nesta fase; governança é invisível ao dev, auditoria fica no operador.
- **Resolução interativa/manual de cada contradição** — a resolução é automática (canônica por recência/confiança) com reversão posterior; sem fila de revisão humana bloqueante.
- **Mudança de modelo de embedding, re-embedding em massa ou grafo de conhecimento** — não são objetivos desta fase.

## Plano de Entrega por Fases

> Escopo desta fase no contexto do roadmap geral (Fases 0–3 da proposta técnica). Aqui, "MVP" = entrega central da Fase 3.

### MVP (núcleo da Fase 3) — Rede de segurança + Guarda-corpos

- Quarentena reversível, proteção de pinadas e trilha de auditoria/reversão.
- Dedup reforçado (escrita + lote) e poda por tempo/uso, automáticos e reversíveis.
- Política global padrão conservadora, ativa por toda a base.

**Critérios de sucesso para avançar:**
- Volume líquido controlado (poda+dedup compensam parte do ingresso) **sem** nenhuma perda irreversível de conhecimento legítimo.
- Operador consegue auditar e reverter ações; memórias pinadas comprovadamente intactas.
- Latência de busca dentro das metas das fases anteriores, sem degradação atribuível aos jobs.

### Incremento — Consolidação semântica (ainda na Fase 3)

- Merge de quase-duplicatas (memória canônica + fontes em quarentena).
- Resolução automática de contradições (canônica por recência/confiança).
- Override de política por projeto.

**Critério para avançar:** redução mensurável de duplicatas semânticas e contradições nos resultados, sem aumento de reversões por merge incorreto além de um limiar aceitável.

### Fases futuras (posterior)

- Cold tier (arquivamento de projetos inativos), busca híbrida no MCP e elasticidade contínua (se houver migração para orquestrador elástico) — iniciativas próprias, fora desta fase.
- Critério de longo prazo: qualidade de memória estável e custo de operação sob controle com centenas de milhões de memórias.

## Métricas de Sucesso

- **Qualidade da recuperação (principal):** queda mensurável na fração de resultados duplicados, contraditórios e obsoletos retornados ao agente, comparada à base pré-governança.
- **Zero perda irreversível:** nenhuma memória legítima perdida de forma irrecuperável; toda ação reversível dentro da janela de quarentena; 100% das memórias pinadas preservadas.
- **Volume sob controle:** crescimento líquido da base estabilizado, com volume recuperado por poda/dedup visível na auditoria.
- **Não regressão de latência:** busca permanece dentro das metas das fases anteriores durante e após a execução dos jobs.
- **Operação sem fricção:** governança ativa por padrão, sem aprovação manual item a item; taxa de reversão por ação incorreta abaixo de um limiar aceitável (especialmente para merge/contradição).
- **Transparência ao dev:** nenhuma mudança de configuração nos agentes MCP e nenhuma reclamação de "sumiço" de conhecimento importante.

## Riscos e Mitigações

- **Risco de adoção — perda de confiança por apagar conhecimento útil:** se a governança remover algo que o dev considerava válido, a confiança na memória cai mais do que o ganho de qualidade. _Mitigação:_ padrões conservadores, poda por idade **e** uso, quarentena reversível, proteção de pinadas, e ativação faseada (guarda-corpos antes do merge semântico).
- **Risco de qualidade — merge/contradição incorretos:** consolidar memórias distintas ou eleger a "canônica" errada degrada em vez de melhorar. _Mitigação:_ limiares conservadores, quarentena (não exclusão) das fontes, auditoria com reversão, e introdução só após validação dos guarda-corpos ([ADR-001](adrs/adr-001.md)).
- **Risco operacional — automação destrutiva sem supervisão suficiente:** jobs automáticos errando em escala. _Mitigação:_ trilha de auditoria, reversão em lote, e limiar de alerta para taxa de reversão; possibilidade de pausar a governança.
- **Risco de cronograma — segundo incremento mais complexo:** a consolidação semântica pode atrasar. _Mitigação:_ o MVP (rede de segurança + guarda-corpos) já entrega valor independente; o merge semântico é incremento separado.
- **Risco de dependência externa — custo da rede de segurança:** quarentena/soft-delete consome armazenamento adicional e processo de expurgo. _Mitigação:_ janela de quarentena dimensionada e expurgo definitivo agendado; registrado em Perguntas em Aberto.
- **Risco competitivo:** soluções gerenciadas (Mem0 Platform, Zep, Letta) oferecem consolidação/esquecimento "prontos". _Mitigação:_ o diferencial é a privacidade self-hosted total com governança equivalente — manter esse valor central.

## Registros de Decisão de Arquitetura

- [ADR-001: Governança de qualidade automática com rede de segurança, faseada](adrs/adr-001.md) — Governança automática (não sob aprovação manual) com soft-delete reversível e proteção de pinadas, entregue em dois incrementos: guarda-corpos de volume (dedup+TTL) antes da consolidação semântica (merge+contradições).

## Perguntas em Aberto

- **Janela de quarentena:** por quantos dias uma memória inativada fica recuperável antes do expurgo definitivo? (impacta custo de armazenamento × segurança de reversão)
- **Limiares da política global padrão:** quais valores conservadores iniciais para idade de poda, tempo desde o último acesso e limiar de similaridade para merge?
- **Critério de "canônica" em contradições:** recência, confiança, frequência de acesso — qual ordem de desempate? E como medir "confiança" de uma memória?
- **Categorias protegidas por padrão:** quais categorias entram como pinadas no padrão global (ex.: `decision`, `security`)?
- **Medição da qualidade da recuperação:** como medir objetivamente a queda de duplicatas/contradições/obsolescência (amostragem auditada, métricas de busca, feedback)? É a métrica-chave e precisa de baseline.
- **Agenda dos jobs:** com que frequência rodar dedup, TTL e consolidação, e qual a janela de "fora de pico" no ambiente Swarm/VMs?
- **Limiar aceitável de reversão:** qual taxa de reversão por merge/contradição incorretos é tolerável antes de pausar/ajustar a consolidação semântica?
- **Responsável pela operação:** qual equipe define a política, monitora a auditoria e responde a alertas de governança?
