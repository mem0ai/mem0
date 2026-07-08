# Mem0 Plugin for NemoClaw — Quickstart

Add persistent long-term memory to your [NemoClaw](https://docs.nvidia.com/nemoclaw/latest/get-started/quickstart.html) OpenClaw agent using the `@mem0/openclaw-mem0` plugin.

> **Note:** This plugin requires **Mem0 Platform mode** (i.e., a Mem0 API key from [app.mem0.ai](https://app.mem0.ai?utm_source=oss&utm_medium=example-nemoclaw)). Open-source mode is not supported in NemoClaw sandboxes because the sandbox proxy blocks `/v1/embeddings` requests required by the open-source backend. See [Known Limitations](#known-limitations) for details.

## Prerequisites

| Resource | Recommended | Minimum |
|----------|-------------|---------|
| CPU      | 4+ vCPU     | 2 vCPU  |
| RAM      | 16 GB       | 8 GB    |
| Disk     | 40 GB free  | 20 GB free |

**Accounts required:**

- **NVIDIA** — sign up at [build.nvidia.com](https://build.nvidia.com), generate an API key at [build.nvidia.com/settings/api-keys](https://build.nvidia.com/settings/api-keys) (starts with `nvapi-`)
- **Mem0** — sign up at [app.mem0.ai](https://app.mem0.ai?utm_source=oss&utm_medium=example-nemoclaw), generate an API key from the dashboard (starts with `m0-`)

**Supported platforms:** Ubuntu 22.04+, macOS (via Docker), Windows (WSL 2 + Docker)

---

## Choose Your Path

### Option A: Full Setup (NemoClaw + Mem0 Plugin)

Use this if you **don't have NemoClaw installed yet**. The script handles everything: Docker, Node.js, NemoClaw installation, onboarding, Mem0 plugin installation, network policy, and configuration.

```bash
# Download
curl -fsSL https://raw.githubusercontent.com/mem0ai/mem0/main/examples/nemoclaw/setup-mem0-nemoclaw.sh -o setup-mem0-nemoclaw.sh

# Run
chmod +x setup-mem0-nemoclaw.sh
./setup-mem0-nemoclaw.sh
```

The script runs through 7 phases:

| Phase | What it does | User input |
|-------|-------------|------------|
| 1 | Prerequisites (Docker, RAM, disk) | None (automatic) |
| 2 | Install NemoClaw | None (automatic) |
| 3 | NemoClaw onboarding (sandbox + k3s) | Sandbox name, NVIDIA API key |
| 4 | Install Mem0 plugin into sandbox | None (automatic) |
| 5 | Update network policy for `api.mem0.ai` | None (automatic) |
| 6 | Configure plugin | Mem0 API key, user ID |
| 7 | Verification | None |

### Option B: Plugin Only (NemoClaw Already Installed)

Use this if you **already have NemoClaw installed and onboarded** with a sandbox in `Ready` state.

```bash
# Download
curl -fsSL https://raw.githubusercontent.com/mem0ai/mem0/main/examples/nemoclaw/install-mem0-plugin.sh -o install-mem0-plugin.sh

# Run
chmod +x install-mem0-plugin.sh
./install-mem0-plugin.sh
```

The script auto-detects your sandbox and runs 3 steps:

| Step | What it does | User input |
|------|-------------|------------|
| 1 | Install Mem0 plugin into sandbox | None (automatic) |
| 2 | Update network policy for `api.mem0.ai` | None (automatic) |
| 3 | Configure plugin | Mem0 API key, user ID |

---

## Verify the Installation

After either script completes, connect to the sandbox and start the gateway:

```bash
source ~/.bashrc
nemoclaw <sandbox-name> connect
nemoclaw-start
```

Look for this line in the startup output:

```
openclaw-mem0: registered (mode: platform, user: your-user-id, graph: false, autoRecall: true, autoCapture: true)
```

You can also verify with:

```bash
openclaw plugins list
```

The `Memory (Mem0)` plugin should show status **loaded**.

## Test the Integration

All test commands run **inside the sandbox**.

### Test 1: Auto-capture (storing memories)

```bash
openclaw agent --agent main --local \
  -m "My name is Alice and I work on distributed systems" \
  --session-id test1
```

Look for: `openclaw-mem0: auto-captured 1 memories`

### Test 2: Auto-recall (retrieving memories across sessions)

Start a **new session** (different `--session-id`):

```bash
openclaw agent --agent main --local \
  -m "What do you know about me?" \
  --session-id test2
```

Look for: `openclaw-mem0: injecting 1 memories into context (1 long-term, 0 session)`

The agent should respond with information from the previous session ("Alice", "distributed systems").

### Test 3: Interactive TUI

```bash
openclaw tui
```

Send messages and the plugin will automatically capture and recall memories in the background.

---

## Plugin Configuration Reference

All options are set inside the sandbox via:

```bash
openclaw config set plugins.entries.openclaw-mem0.config.<key> <value>
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `mode` | `"platform"` \| `"open-source"` | `"platform"` | Backend mode |
| `apiKey` | string | — | Mem0 API key (starts with `m0-`) |
| `userId` | string | `"default"` | Unique identifier for the user |
| `autoRecall` | boolean | `true` | Inject memories before each agent turn |
| `autoCapture` | boolean | `true` | Store facts after each agent turn |
| `topK` | number | `5` | Max memories per recall |
| `searchThreshold` | number | `0.3` | Min similarity score (0-1) |
| `orgId` | string | — | Mem0 organization ID |
| `projectId` | string | — | Mem0 project ID |
| `enableGraph` | boolean | `false` | Enable entity graph for relationships |
| `customInstructions` | string | — | Rules for what Mem0 should store/exclude |

## Agent Memory Tools

Once the plugin is active, the agent can use these tools during conversations:

| Tool | Description |
|------|-------------|
| `memory_search` | Search memories by natural language |
| `memory_list` | List all stored memories for a user |
| `memory_store` | Explicitly save a fact |
| `memory_get` | Retrieve a memory by ID |
| `memory_forget` | Delete by ID or by query |

## CLI Commands

Run these inside the sandbox:

```bash
# Search all memories (long-term + session)
openclaw mem0 search "what languages does the user know"

# Search only long-term memories
openclaw mem0 search "user preferences" --scope long-term

# Search only session memories
openclaw mem0 search "current task" --scope session

# Memory stats
openclaw mem0 stats
```

---

## Troubleshooting

For detailed troubleshooting steps, see the [troubleshooting guide](troubleshooting-guide.pdf) included in this directory.

### Common Issues

#### `npm tar TAR_ENTRY_ERROR ENOENT` during NemoClaw installation

This is a known npm bug where concurrent tar extraction races cause `ENOENT` errors on deeply nested packages. The `setup-mem0-nemoclaw.sh` script works around this by cloning the NemoClaw repo and installing with `--maxsockets=1` to serialize downloads. If you installed NemoClaw manually and hit this error:

```bash
git clone --depth 1 https://github.com/NVIDIA/NemoClaw.git ~/.nemoclaw-src
cd ~/.nemoclaw-src
npm install --maxsockets=1
npm link
```

#### `sandbox not found` during onboarding step 7

The gateway restarted during onboarding and lost the sandbox state. Re-run `nemoclaw onboard`. When prompted that the sandbox already exists, choose `y` to recreate it.

#### `npm error 403 Forbidden` when installing plugin inside sandbox

The OpenShell gateway's TLS proxy blocks scoped npm packages (the `%2f` in the URL). Use the manual installation method (Method 2 in the scripts) which downloads outside the sandbox and uploads the tarball.

#### `capture failed: Connection error` or `recall failed: Connection error`

The network policy is not applied or missing the `mem0_api` entry. Re-run the plugin install script or manually apply the policy:

```bash
openshell policy set <sandbox-name> --policy /tmp/nemoclaw-mem0-policy.yaml --wait
```

#### `Telemetry event capture failed: TypeError: fetch failed`

This is harmless. The Mem0 SDK's telemetry endpoint (`us.i.posthog.com`) is blocked by the sandbox proxy. It does not affect memory functionality.

#### Plugin shows `disabled` in `openclaw plugins list`

The memory slot is not set to `openclaw-mem0`. Inside the sandbox, run:

```bash
openclaw config set plugins.slots.memory openclaw-mem0
```

#### `K8s namespace not ready` on Ubuntu 24.04

Ubuntu 24.04 defaults to cgroup v2 which causes k3s (used by NemoClaw) to fail. Apply the cgroup fix:

```bash
sudo python3 -c "
import json, os
p = '/etc/docker/daemon.json'
c = json.load(open(p)) if os.path.exists(p) else {}
c['default-cgroupns-mode'] = 'host'
json.dump(c, open(p, 'w'), indent=2)
"
sudo systemctl restart docker
```

Then re-run `nemoclaw onboard`.

### Known Limitations

**Open-source mode is not supported in NemoClaw sandboxes.** The Mem0 open-source mode requires calling `/v1/embeddings` on an external LLM provider. NemoClaw's sandbox proxy intercepts all OpenAI-compatible API requests but only allows `/v1/chat/completions` through. Use **platform mode** instead.

---

## Files in This Directory

| File | Description |
|------|-------------|
| `setup-mem0-nemoclaw.sh` | Full setup script (NemoClaw + Mem0 plugin) |
| `install-mem0-plugin.sh` | Plugin-only install script (NemoClaw already set up) |
| `troubleshooting-guide.pdf` | Detailed setup and troubleshooting guide |
| `quickstart.md` | This file |

## Links

- [Mem0 Documentation](https://docs.mem0.ai)
- [NemoClaw Documentation](https://docs.nvidia.com/nemoclaw/latest/get-started/quickstart.html)
- [`@mem0/openclaw-mem0` on npm](https://www.npmjs.com/package/@mem0/openclaw-mem0)
- [Mem0 Dashboard](https://app.mem0.ai?utm_source=oss&utm_medium=example-nemoclaw)
