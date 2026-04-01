# OpenClaw + Mem0 One-Click Docker Setup

Get a working OpenClaw agent with Mem0 persistent memory in under 2 minutes.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine with Compose v2
- One of:
  - **Platform mode**: A Mem0 API key from [app.mem0.ai](https://app.mem0.ai)
  - **OSS mode**: An OpenAI API key

## Quick Start

```bash
git clone https://github.com/mem0ai/mem0 && cd mem0/openclaw/docker
./setup.sh
```

The setup script will:
1. Ask you to choose Platform or Open-Source mode
2. Prompt for your API key(s)
3. Start the containers automatically

Then open **http://localhost:18789** to start chatting.

## What Gets Deployed

### Platform Mode
```
┌─────────────────────────┐
│  OpenClaw (port 18789)  │
│  + Mem0 Plugin          │──→  Mem0 Cloud (app.mem0.ai)
└─────────────────────────┘
```

### OSS Mode
```
┌─────────────────────────┐     ┌─────────────────┐
│  OpenClaw (port 18789)  │     │  Qdrant          │
│  + Mem0 Plugin          │────→│  (port 6333)     │
└─────────────────────────┘     │  Vector Storage  │
                                └─────────────────┘
```

## Modes Explained

| Feature | Platform (Mem0 Cloud) | Open-Source (Self-Hosted) |
|---------|----------------------|--------------------------|
| Setup | API key only | API key + Qdrant container |
| Vector storage | Managed by Mem0 | Local Qdrant |
| LLM for extraction | Managed by Mem0 | Your OpenAI key |
| Graph memory | Supported | Not yet |
| Dashboard | app.mem0.ai | CLI commands |

## Configuration

After setup, your config lives at `~/.openclaw/openclaw.json`. You can edit it directly.

Key settings in the `openclaw-mem0` plugin section:

| Setting | Default | Description |
|---------|---------|-------------|
| `autoCapture` | `true` | Auto-store conversation facts |
| `autoRecall` | `true` | Auto-retrieve relevant memories |
| `searchThreshold` | `0.5` | Minimum similarity score (0-1) |
| `topK` | `5` | Max memories to retrieve |

To change the port or other Docker settings, edit `.env` in this directory.

## Troubleshooting

**Port 18789 already in use**
```bash
lsof -i :18789
# Kill the process or change OPENCLAW_PORT in .env
```

**API key errors**
- Platform: Verify your key at [app.mem0.ai](https://app.mem0.ai)
- OSS: Ensure `OPENAI_API_KEY` is valid and has credits

**Containers won't start**
```bash
docker compose logs
# or for OSS mode:
docker compose -f docker-compose.yml -f docker-compose.oss.yml logs
```

**Docker not found**
Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) or follow the [engine install guide](https://docs.docker.com/engine/install/).

**Plugin not loading**
```bash
# Reinstall the plugin manually
docker compose run --rm openclaw openclaw plugins install @mem0/openclaw-mem0
```

## Links

- [Mem0 Documentation](https://docs.mem0.ai)
- [Mem0 OpenClaw Plugin](https://github.com/mem0ai/mem0/tree/main/openclaw)
- [OpenClaw Documentation](https://openclaw.com/docs)
