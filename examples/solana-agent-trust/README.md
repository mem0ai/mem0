# Solana Agent Trust + Persistent Memory

Combines [mem0](https://mem0.ai) persistent memory with the
[TWZRD Agent Intel](https://intel.twzrd.xyz) MCP server to build an AI
assistant that **remembers verified Solana agent wallets** across sessions.

## What It Does

- **Trust verification**: Calls the TWZRD MCP server to score a Solana wallet
  (`score_agent`) and run a preflight check (`preflight_check`)
- **Memory caching**: Stores trust results in mem0 so repeat checks for the
  same wallet skip the MCP call entirely
- **Persistent history**: Builds a local trust database across conversations

## Setup

```bash
pip install mem0ai mcp openai
```

```bash
export MEM0_API_KEY=your_key     # from app.mem0.ai
export OPENAI_API_KEY=your_key
```

## Run

```bash
python solana_agent_trust.py
```

Then try:

```
Check wallet D1QkbFJKiPsymJ65RKHhF6DFB8sPMfpBaFBzuHKfJGWi
```

On the second run, mem0 returns the cached result without hitting the MCP server.

## MCP Server

| Tool | Description | Cost |
|------|-------------|------|
| `score_agent` | Trust score 0–1 + x402 payment count | Free |
| `preflight_check` | APPROVE/REJECT with reasoning | Free |
| `get_trust_receipt` | Signed on-chain trust receipt | HTTP 402 |

```json
{
  "mcpServers": {
    "twzrd-agent-intel": {
      "url": "https://intel.twzrd.xyz/mcp"
    }
  }
}
```

## How It Works

```
User asks about wallet
       │
       ▼
mem0.search(wallet)  ──── cache hit ──► return cached result
       │
   cache miss
       │
       ▼
TWZRD MCP: score_agent + preflight_check
       │
       ▼
mem0.add(result)  ──► stored for next session
       │
       ▼
Return trust decision
```
