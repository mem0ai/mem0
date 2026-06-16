---
name: mode
description: Define como a memória mem0 opera automaticamente — escolhe entre os 3 modos (ler+gravar, só ler, ou nada sem solicitação). Use quando o usuário quiser mudar a automação de memória, ativar/desativar captura automática, controlar privacidade de leitura/escrita, ou perguntar "como o mem0 está gravando/lendo". Não altera o MCP (que continua disponível nos 3 modos) — só os hooks automáticos.
---

# Mem0 — Modo de memória

Controla a **automação** dos hooks de memória, gravando um preset em
`~/.mem0/settings.json`. O servidor MCP e os comandos manuais (`/mem0:remember`,
`/mem0:peek`, `search_memories`) funcionam nos **três** modos — o modo só decide
o que acontece **automaticamente**, sem o usuário pedir.

## Os 3 modos

| Modo | `auto_search` | `auto_save` | Efeito |
|------|:---:|:---:|--------|
| **1. Sempre ler e gravar** | `true` | `true` | Busca memórias e captura aprendizados automaticamente. |
| **2. Sempre ler, gravar só se solicitado** | `true` | `false` | Injeta contexto automático; só grava via `/mem0:remember` ou "lembre disso". |
| **3. Nunca sem solicitação** | `false` | `false` | Nada automático; tudo manual via comandos `/mem0:*` e MCP. |

Default recomendado (mais conservador em privacidade): **Modo 2**.

## Execução

### 1. Mostrar o modo atual

```bash
python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.mem0/settings.json")
s = {}
if os.path.exists(p):
    try:
        s = json.load(open(p))
    except Exception:
        s = {}
asch = s.get("auto_search", True)
asav = s.get("auto_save", True)
mode = "1 (ler+gravar)" if (asch and asav) else \
       "2 (ler; gravar manual)" if (asch and not asav) else \
       "3 (manual)" if (not asch and not asav) else \
       f"customizado (auto_search={asch}, auto_save={asav})"
print(f"Modo atual: {mode}")
PY
```

### 2. Apresentar as opções

Mostre os 3 modos da tabela e pergunte qual o usuário quer (se ele já indicou
na mensagem, pule a pergunta).

### 3. Gravar a escolha

Aplique o preset do modo escolhido (faz **merge**, preserva as outras chaves):

```bash
# Substitua AUTO_SEARCH e AUTO_SAVE pelos valores do modo escolhido (true/false).
AUTO_SEARCH=true
AUTO_SAVE=false
python3 - "$AUTO_SEARCH" "$AUTO_SAVE" <<'PY'
import json, os, sys
auto_search = sys.argv[1].lower() == "true"
auto_save = sys.argv[2].lower() == "true"
p = os.path.expanduser("~/.mem0/settings.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
s = {}
if os.path.exists(p):
    try:
        s = json.load(open(p))
    except Exception:
        s = {}
s["auto_search"] = auto_search
s["auto_save"] = auto_save
json.dump(s, open(p, "w"), indent=2)
open(p, "a").write("\n")
print(f"OK — auto_search={auto_search}, auto_save={auto_save} gravado em {p}")
PY
```

### 4. Confirmar

Mostre o novo modo e lembre o usuário: a troca vale a partir da **próxima**
mensagem/sessão (os hooks leem `settings.json` no início de cada execução), e
**não reinstala nem altera o MCP**.
