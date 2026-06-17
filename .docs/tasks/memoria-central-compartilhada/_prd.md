# PRD — Memória Central Compartilhada Local-First

## Visão Geral

Times grandes de desenvolvimento usam múltiplos agentes de IA (em IDEs, terminais, automações) que hoje esquecem tudo entre sessões e não compartilham conhecimento entre si nem entre pessoas. Cada agente reaprende o mesmo contexto, e decisões, convenções e fatos do projeto se perdem.

Este produto transforma o projeto em uma **memória central compartilhada que roda 100% na rede local**, onde qualquer agente de IA se conecta via **MCP** para **consultar e gravar memórias permanentes**. As memórias são organizadas em **espaços/projetos auto-gerenciados**, escritas com **extração automática de fatos por LLM local**, e disponíveis a todos os agentes da rede local.

- **Qual problema resolve:** perda de contexto entre sessões/agentes, retrabalho de reaprendizado e ausência de conhecimento compartilhado entre devs e seus agentes — sem expor dados a serviços externos.
- **Para quem é:** times grandes de desenvolvimento (200+ devs) e os agentes de IA que operam na mesma rede local.
- **Por que é valioso:** acelera os agentes com contexto compartilhado e confiável, com **privacidade total** (nenhum dado sai da rede local) e **baixa latência** (a rede local elimina o "imposto" de 50–300 ms da nuvem).

## Objetivos

- **Compartilhamento:** qualquer agente da rede local recupera memórias gravadas por qualquer outro agente/usuário, organizadas por projeto.
- **Privacidade:** 100% local — inferência (LLM), embeddings e armazenamento na rede local; zero telemetria ou tráfego externo.
- **Velocidade:** leitura com latência percebida baixa (alvo de busca p95 abaixo de ~200 ms na rede local) e escrita que não bloqueia o fluxo do agente.
- **Disponibilidade via MCP:** instalação única na rede local que expõe a memória a qualquer agente compatível com MCP, com autoconfiguração da conexão.
- **Escala:** suportar 200+ desenvolvedores e seus agentes, com múltiplos espaços auto-gerenciados.
- **Marco-alvo:** MVP utilizável por um time-piloto em torno de uma janela de ~8–10 semanas (a confirmar na TechSpec).

## Histórias de Usuário

**Persona principal — Desenvolvedor (com seus agentes):**
- Como dev, quero que meus agentes gravem decisões e fatos do projeto para que eu e o time não precisemos reexplicá-los.
- Como dev, quero que meu agente recupere o conhecimento já registrado pelo time para responder com o contexto certo na hora.
- Como dev, **não preciso fazer login**: minha máquina é identificada automaticamente pelo nome na rede local ao gravar/buscar memórias.
- Como dev, quero apontar meu agente a um único endereço da rede local e que a conexão se configure sozinha.

**Persona — Agente de IA (cliente MCP):**
- Como agente, quero consultar um endereço local e obter automaticamente os dados de conexão para me ligar à memória via MCP sem configuração manual.
- Como agente, quero gravar uma memória enviando o contexto e receber confirmação rápida sem travar minha tarefa.
- Como agente, quero buscar memórias relevantes por similaridade semântica no contexto do projeto atual.
- Como agente, quero buscar em qualquer projeto da empresa, pois o conhecimento é compartilhado em toda a rede local.
- Como agente, quero listar e remover memórias quando necessário.

**Persona secundária — Administrador da instalação:**
- Como admin, quero instalar o serviço na rede local definindo o LLM e o embedder locais.
- Como admin, **não preciso criar nem gerenciar espaços** — a memória os cria e cataloga sozinha por projeto.
- Como admin, quero ver um registro de acessos (qual máquina leu/gravou o quê e quando).

**Casos de borda:**
- Dois agentes gravam fatos contraditórios no mesmo projeto (tratado pela política de conflito).
- O LLM local fica indisponível durante uma escrita (degradação previsível).
- A memória classifica uma operação no projeto errado (atribuição de espaço incorreta).
- Máquinas com nomes duplicados ou genéricos na rede.

## Funcionalidades Principais

**P0 — Essenciais ao MVP**

1. **Espaços/Projetos de memória auto-gerenciados** — Cada espaço representa um projeto da empresa e é **criado e catalogado automaticamente pela própria memória** (sem criação manual). Serve para organizar e contextualizar as memórias, mantendo a relevância da busca por projeto.
2. **Catalogação interna de projetos** — A memória identifica o projeto associado a cada operação e materializa/atualiza o espaço correspondente, mantendo um catálogo interno dos projetos existentes.
3. **Gravação com extração automática por LLM** — O agente envia conversa/contexto; o LLM local extrai os fatos relevantes e os persiste no projeto. A confirmação ao agente é rápida (escrita não bloqueante).
4. **Busca semântica compartilhada** — Recuperação por similaridade no contexto do projeto, retornando memórias de qualquer agente/usuário, priorizando relevância e recência.
5. **Acesso via MCP** — Ferramentas MCP para gravar, buscar, listar e remover memórias, consumíveis por qualquer agente compatível na rede local.
6. **Auto-descoberta de conexão MCP** — Um **endereço conhecido na rede local** fornece aos agentes os dados necessários (endpoint, parâmetros, contexto) para que eles **montem sozinhos** a conexão MCP com a memória, sem configuração manual.
7. **Acesso aberto na rede local** — Qualquer agente conectado na rede local pode ler e escrever em qualquer projeto. O espaço dá contexto, não restringe acesso. A fronteira de privacidade é a rede local como um todo.
8. **Política de conflito "manter ambas + recente vence"** — Fatos contraditórios coexistem; a busca prioriza a versão mais recente, preservando o histórico.
9. **Stack 100% local** — LLM e embedder locais definidos na instalação; armazenamento local; sem chamadas externas.
10. **Instalação única na rede local** — Pacote auto-contido implantável em um servidor da rede, pronto para receber conexões de agentes.

**P1 — Importantes, pós-MVP imediato**

11. **Identificação por nome da máquina** — Cada operação é identificada pelo **nome da máquina local (hostname)** que originou a chamada. Não há cadastro/login: o hostname serve como identidade leve para atribuição e auditoria, no modelo de confiança da rede local.
12. **Registro de acessos (auditoria básica)** — Trilha de qual máquina leu/gravou/removeu o quê e quando.

**Interação entre funcionalidades:** o projeto (espaço) é a fronteira de contexto; a busca e a gravação operam contextualizadas ao projeto, mas o acesso é aberto na rede local; a auto-descoberta liga o agente; a identificação por hostname alimenta a auditoria.

## Experiência do Usuário

**Onboarding (admin):** instala o serviço na rede local e informa o LLM e o embedder locais. **Não há criação manual de espaços**: ao operar, a memória reconhece o projeto e cria/cataloga o espaço automaticamente.

**Conexão do agente (auto-servida):** o agente acessa o **endereço local de descoberta**, obtém os dados de conexão e se liga à memória via MCP automaticamente, identificando-se pelo **nome da máquina**. Sem etapa de cadastro/login.

**Fluxo principal — gravar:** o agente, ao longo da tarefa, envia o contexto; o sistema extrai os fatos, associa ao projeto e confirma rapidamente; o conhecimento fica disponível ao time.

**Fluxo principal — buscar:** o agente consulta antes de agir; recebe memórias relevantes (de qualquer agente), com a versão mais recente priorizada.

**Considerações de UX:** latência baixa o suficiente para não interromper o raciocínio do agente; comportamento previsível quando o LLM local está sob carga; autoconfiguração sem fricção.

## Restrições Técnicas de Alto Nível

- **Privacidade obrigatória:** nenhum dado pode trafegar para fora da rede local; sem telemetria/usage reporting externo.
- **LLM e embeddings locais:** definidos no momento da instalação.
- **Disponibilidade via MCP:** o protocolo de acesso é MCP, para qualquer agente da rede local, com autoconfiguração via endereço de descoberta.
- **Metas de desempenho (perspectiva do usuário):** busca p95 abaixo de ~200 ms na rede local sob carga típica; escrita não bloqueante.
- **Escala:** 200+ usuários e seus agentes, com múltiplos projetos auto-gerenciados.

## Fora de Escopo (Non-Goals)

- Autenticação forte / SSO / LDAP / Active Directory (MVP usa confiança na rede local e identificação por hostname).
- Criação e administração manual de espaços (a memória os auto-cria e cataloga).
- Pertencimento/restrição de acesso por espaço (todos os agentes da rede local acessam todos os projetos no MVP).
- Papéis granulares (leitor/editor/admin) dentro do projeto.
- Resolução de conflito por revisão humana ou versionamento com time-travel/branching avançado.
- Sincronização com nuvem, multi-site ou acesso fora da rede local.
- Dashboard visual rico de governança/analytics (auditoria no MVP é registro básico).
- Gravação literal manual como modo primário (o MVP foca na extração automática por LLM).
- Suporte a LLMs hospedados na nuvem.

## Plano de Entrega por Fases

### MVP (Fase 1)
- Espaços/projetos auto-criados e catalogados pela memória; gravação com extração automática por LLM local; busca semântica compartilhada; acesso via MCP; auto-descoberta de conexão MCP via endereço local; acesso aberto na rede local; política "manter ambas + recente vence"; stack 100% local; instalação única.
- **Critérios para avançar:** time-piloto conecta agentes via MCP com autoconfiguração; grava e recupera memórias compartilhadas por projeto; busca p95 dentro da meta; nenhum tráfego externo observado.

### Fase 2
- Identificação por nome da máquina consolidada e **registro de acessos (auditoria básica)**.
- Refino da estratégia de catalogação/atribuição de projetos.
- **Critérios para avançar:** auditoria utilizável por hostname; atribuição de projeto confiável no piloto.

### Fase 3
- Governança avançada (papéis e restrição de acesso por projeto, dashboard), autenticação mais forte (SSO/diretório), e tratamento de staleness/conflito mais sofisticado.
- **Critérios de longo prazo:** adoção ampla entre times, com governança e privacidade sustentadas em escala.

## Métricas de Sucesso

- **Adoção:** nº de máquinas (hostnames) distintas ativas conectadas via MCP por semana; nº de projetos ativos catalogados.
- **Onboarding:** autoconfiguração da conexão MCP sem intervenção manual (passos = 0 após apontar o endereço).
- **Compartilhamento:** % de buscas que retornam memórias gravadas por outra máquina/agente (prova de valor compartilhado).
- **Desempenho:** latência p95 de busca na rede local; latência de confirmação de escrita.
- **Privacidade:** zero conexões de saída para fora da rede local (verificável).
- **Qualidade:** taxa de buscas com resultado relevante; taxa de atribuição correta de projeto; taxa de memórias obsoletas reportadas.
- **Impacto:** redução percebida de retrabalho/reexplicação de contexto pelo time-piloto.

## Riscos e Mitigações

- **Adoção:** se conectar agentes for trabalhoso, o uso não decola. *Mitigação:* auto-descoberta e autoconfiguração da conexão MCP; piloto guiado.
- **Confiança no conteúdo compartilhado:** memórias obsoletas ou ruído reduzem a confiança. *Mitigação:* priorização por recência e métrica de relevância; revisão de staleness em fase futura.
- **Exposição entre projetos:** como todos acessam todos os projetos, contexto sensível fica visível a toda a rede local. *Mitigação:* restringir a implantação a redes confiáveis; controle de acesso por projeto como item de fase futura.
- **Atribuição incorreta de projeto:** a auto-catalogação pode classificar memórias no projeto errado. *Mitigação:* sinal claro de projeto na operação e revisão da estratégia no piloto.
- **Concorrência em escala:** 200+ devs podem pressionar leitura/escrita. *Mitigação:* metas de p95 e validação de carga antes do rollout amplo.
- **Competitivo:** alternativas locais (OpenMemory, Supermemory) e gerenciadas (Mem0, Zep) existem. *Mitigação:* foco no diferencial "time + local + projetos auto-gerenciados" via MCP.
- **Dependência do LLM local:** desempenho da extração depende do modelo escolhido na instalação. *Mitigação:* orientar modelos recomendados e tornar a escrita não bloqueante.

## Registros de Decisão de Arquitetura

- [ADR-001: Evoluir o OpenMemory (MCP-first) para Memória Central Compartilhada Multi-Espaço](adrs/adr-001.md) — Adotar a evolução do servidor MCP e da stack local existentes, em vez de uma plataforma completa nova ou um greenfield minimalista.
- [ADR-002: Espaços auto-criados e auto-gerenciados por projeto, com acesso aberto a todos os agentes da rede local](adrs/adr-002.md) — Espaços = projetos da empresa, auto-criados e catalogados pela memória, acessíveis a todos os agentes da rede local (lê+escreve), sem pertencimento restrito.

## Perguntas em Aberto

- **Sinal de projeto:** o que determina a qual projeto/espaço uma operação pertence (identificador enviado pelo agente, inferência por conteúdo, diretório de trabalho)?
- **Reclassificação:** é possível corrigir/mesclar espaços auto-criados catalogados incorretamente?
- **Descoberta do endereço:** como o agente conhece o endereço local de descoberta na primeira vez (configuração mínima inicial, padrão de rede, anúncio na rede)?
- **Colisão/anonimato de hostname:** como tratar máquinas com nomes duplicados ou genéricos, e isso é suficiente para a auditoria desejada?
- **Modelos locais recomendados:** quais LLM/embedder locais serão padrão na instalação para equilibrar qualidade de extração e latência?
- **Retenção/expiração:** memórias permanentes têm política de retenção ou expiram? (impacta staleness)
- **Limites de escala por projeto:** existe volume máximo esperado de memórias por projeto que afete a meta de latência?
- **Meta de latência de escrita:** qual o tempo máximo aceitável de confirmação ao agente quando a extração por LLM ocorre de forma assíncrona?
