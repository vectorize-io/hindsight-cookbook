---
description: "Give Cursor 3 persistent memory across sessions using the Hindsight Cursor plugin"
tags: { sdk: "hindsight-cursor", topic: "Agents" }
---

# Cursor Memory

Give [Cursor](https://cursor.com) persistent memory across sessions using the Hindsight Cursor plugin. The plugin recalls relevant project context at session start and retains conversation transcripts after each task, so Cursor 3 agents can pick up where they left off.

## What This Demonstrates

- **Session recall** — Hindsight injects relevant project memories at the start of each Cursor session via the `sessionStart` hook
- **On-demand MCP tools** — the agent can use `recall`, `retain`, and `reflect` tools mid-session for deeper memory lookups
- **Automatic retain** — Cursor task transcripts are stored to Hindsight after each task via `stop`
- **Cross-session continuity** — Cursor remembers project context, preferences, and decisions across separate chats
- **Cursor 3 workflow fit** — works with the new Agents Window, rules, and skills model
- **Per-project or per-session isolation** — optional dynamic bank IDs keep memory scoped however you want

## Prerequisites

1. **Cursor 3** with plugin support enabled
2. **Python 3.9+** with `uv` or `pip` to run the demo scripts
   ```bash
   python3 --version
   ```
3. **A running Hindsight API**
   - Local: `http://localhost:8888`
   - Or Hindsight Cloud / self-hosted API

## Quick Start

### 1. Install the Cursor plugin

```bash
pip install hindsight-cursor
cd /path/to/your-project
hindsight-cursor init --api-url http://localhost:8888
```

**Using Hindsight Cloud instead?** [Sign up](https://ui.hindsight.vectorize.io/signup) and create an API key under **Settings > API Keys**, then:

```bash
hindsight-cursor init --api-url https://api.hindsight.vectorize.io --api-token YOUR_HINDSIGHT_API_TOKEN
```

> If Cursor is already open, **fully quit and reopen it** after adding the plugin. Plugins load at startup.

### 2. Seed the demo bank

For local Hindsight:

```bash
uv run --with hindsight-client python seed_memory.py --reset
```

For Hindsight Cloud, export your connection details first:

```bash
export HINDSIGHT_URL=https://api.hindsight.vectorize.io
export HINDSIGHT_API_KEY=YOUR_HINDSIGHT_API_TOKEN
uv run --with hindsight-client python seed_memory.py --reset
```

### 3. Verify the seed data

```bash
uv run --with hindsight-client python verify_memory.py
```

### 4. Open Cursor 3

Open the target project in Cursor and start a conversation. Ask questions like:

- `What testing framework do I prefer for Python work?`
- `What stack is this project using?`
- `What coding style do I usually prefer?`

The plugin injects matching memories at session start, and the agent can use MCP tools for deeper lookups mid-session.

## Files

| File | Description |
|------|-------------|
| `seed_memory.py` | Seeds sample developer facts for the Cursor memory demo |
| `verify_memory.py` | Queries Hindsight directly to verify the seed and recall flow |
| `requirements.txt` | Optional dependencies if you prefer `pip install -r requirements.txt` |

## Notes

- Use `dynamicBankId: true` with `["agent", "project"]` to isolate memory per repository.
- Use `["session"]` if you want one bank per Cursor conversation.
- The `init` command also sets up `.cursor/mcp.json` for on-demand MCP tools (`recall`, `retain`, `reflect`). Use `--no-mcp` to skip this.
