<p align="center">
  <a href="https://github.com/mem0ai/mem0">
    <img src="docs/images/banner-sm.png" width="800px" alt="Mem0 - The Memory Layer for Personalized AI">
  </a>
</p>

<p align="center">
  <a href="https://github.com/mem0ai/mem0/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/mem0ai/mem0/ci.yml?branch=main&label=build&style=flat-square" alt="Build status">
  </a>
  <a href="https://github.com/mem0ai/mem0/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/mem0ai/mem0?style=flat-square" alt="License">
  </a>
  <a href="https://stripe.com">
    <img src="https://img.shields.io/badge/Powered%20by-Stripe-635BFF?style=flat-square&logo=stripe" alt="Stripe">
  </a>
  <a href="https://trendshift.io/repositories/11194" target="blank">
    <img src="https://trendshift.io/api/badge/repositories/11194" alt="Trendshift" width="200" height="44"/>
  </a>
</p>

<p align="center">
  <a href="https://mem0.ai">Website</a>
  ·
  <a href="https://docs.mem0.ai">Docs</a>
  ·
  <a href="https://mem0.dev/DiG">Discord</a>
  ·
  <a href="https://mem0.dev/demo">Demo</a>
  ·
  <a href="https://app.mem0.ai">Cloud Console</a>
</p>

<p align="center">
  <a href="https://pepy.tech/project/mem0ai">
    <img src="https://img.shields.io/pypi/dm/mem0ai?style=flat-square" alt="PyPI downloads">
  </a>
  <a href="https://github.com/mem0ai/mem0">
    <img src="https://img.shields.io/github/commit-activity/m/mem0ai/mem0?style=flat-square" alt="Commit activity">
  </a>
  <a href="https://pypi.org/project/mem0ai">
    <img src="https://img.shields.io/pypi/v/mem0ai?color=%2334D058&label=pypi&style=flat-square" alt="PyPI version">
  </a>
  <a href="https://www.npmjs.com/package/mem0ai">
    <img src="https://img.shields.io/npm/v/mem0ai?style=flat-square" alt="npm version">
  </a>
  <a href="https://www.ycombinator.com/companies/mem0">
    <img src="https://img.shields.io/badge/Y%20Combinator-S24-orange?style=flat-square" alt="YC S24">
  </a>
</p>

---

## Quick Start

```bash
pip install mem0ai
```

```python
from mem0 import Memory

memory = Memory()
memory.add("I love hiking and outdoor activities", user_id="alice")
results = memory.search("What does alice like?", user_id="alice")
print(results)
```

[Full quickstart guide →](https://docs.mem0.ai/quickstart)

## Pricing

| Tier | Price | Includes |
|------|-------|----------|
| **Free** | $0 | 1k calls/mo, 1 project |
| **Starter** | $5/mo | 50k calls, 3 projects |
| **Pro** | $10/mo | 200k calls/mo, unlimited projects, webhooks |
| **Founder** | **$3/mo lifetime** | Same as Pro, first 20 buyers only |

Billed securely via [Stripe](https://stripe.com). [View plans →](https://mem0.ai/pricing)

## New Memory Algorithm (April 2026)

| Benchmark | Old | New | Tokens | Latency p50 |
|-----------|-----|-----|--------|-------------|
| **LoCoMo** | 71.4 | **91.6** | 7.0K | 0.88s |
| **LongMemEval** | 67.8 | **93.4** | 6.8K | 1.09s |
| **BEAM (1M)** | — | **64.1** | 6.7K | 1.00s |
| **BEAM (10M)** | — | **48.6** | 6.9K | 1.05s |

Single-pass retrieval, no agentic loops. [Read the paper →](https://mem0.ai/research)

## Features

- **Multi-Level Memory** — User, Session, and Agent state with adaptive personalization
- **Cross-Platform SDKs** — Python, Node.js, CLI
- **Self-Hosted or Cloud** — `docker compose up` or managed at [app.mem0.ai](https://app.mem0.ai)
- **Hybrid Search** — Semantic + BM25 + entity boosting for best retrieval

## Integrations

| Integration | Description | Link |
|-------------|-------------|------|
| ChatGPT Extension | Store memories across ChatGPT, Perplexity, Claude | [Chrome](https://chromewebstore.google.com/detail/onihkkbipkfeijkadecaafbgagkhglop) |
| LangGraph | Build customer bots with memory | [Guide](https://docs.mem0.ai/integrations/langgraph) |
| CrewAI | Tailor CrewAI outputs with Mem0 | [Example](https://docs.mem0.ai/integrations/crewai) |

## License

Apache 2.0 — see [LICENSE](https://github.com/mem0ai/mem0/blob/main/LICENSE).
