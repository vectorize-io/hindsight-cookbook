---
description: "Give Roo Code persistent memory across sessions using Hindsight MCP"
tags: { sdk: "hindsight-roo-code", topic: "Agents" }
---

# Roo Code Memory

Give [Roo Code](https://github.com/RooVetGit/Roo-Code) persistent memory across sessions using Hindsight. A one-command installer registers Hindsight's MCP server and injects a custom rules file that teaches Roo to recall context before each task and retain learnings after — no changes to your workflow required.

## What This Demonstrates

- **Automatic recall** — Hindsight injects relevant memories at the start of every Roo task via custom rules
- **Session retention** — decisions and discoveries are stored to Hindsight at task end
- **Cross-session continuity** — Roo remembers project context, preferences, and past decisions between sessions
- **Per-project isolation** — memory is scoped to the current project by default (or global with `--global`)
- **Zero workflow changes** — install once; memory works through Roo's existing MCP tool mechanism

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     Roo Code                        │
│                                                     │
│  New task starts                                    │
│      │                                              │
│      ▼                                              │
│  Rules file ──→ recall (hindsight MCP) ──→ inject  │
│      │              │                               │
│      │         [relevant facts from past sessions]  │
│      ▼                                              │
│  Roo sees task + memory context                     │
│      │                                              │
│      ▼ (during/after task)                          │
│  retain (hindsight MCP) ──→ Hindsight API ──→ store │
└─────────────────────────────────────────────────────┘
```

The installer writes two files:
- **`.roo/mcp.json`** — registers Hindsight's `/mcp` endpoint as an MCP server, with `recall` and `retain` auto-approved
- **`.roo/rules/hindsight-memory.md`** — instructions injected into every Roo system prompt

## Prerequisites

1. **Roo Code** — install from the VS Code marketplace

2. **Python 3.9+**
   ```bash
   python3 --version
   ```

3. **Hindsight** — cloud or local
   - [Hindsight Cloud](https://hindsight.vectorize.io) (sign up for an API key)
   - Or run locally: `pip install hindsight-all && hindsight-api`

## Quick Start

### 1. Install the Roo Code Hindsight integration

```bash
git clone https://github.com/vectorize-io/hindsight.git
cd hindsight/hindsight-integrations/roo-code
python install.py
```

For Hindsight Cloud:
```bash
python install.py --api-url https://api.hindsight.vectorize.io
```

For a global install (all projects):
```bash
python install.py --global
```

### 2. Restart Roo Code

After installing, restart VS Code or reload the window. Check **Settings → MCP Servers** — `hindsight` should appear as connected.

### 3. (Optional) Seed your memory bank

To see recall working immediately without waiting for sessions to build up:

```bash
pip install -r requirements.txt

# Point to your Hindsight instance
export HINDSIGHT_URL=https://api.hindsight.vectorize.io
export HINDSIGHT_API_KEY=hsk_your_token_here

python seed_memory.py
```

### 4. Start a task in Roo Code

Ask something like `what testing framework do I prefer?` — Roo will call `recall` and Hindsight will inject the relevant context before the model responds.

## How It Works

### Rules file — `hindsight-memory.md`

The installer copies `rules/hindsight-memory.md` to `.roo/rules/hindsight-memory.md`, which Roo Code injects into every system prompt. The rules instruct Roo to:

- **At task start**: call `recall` (hindsight server) with a query summarizing the current task
- **During a task**: call `retain` (hindsight server) for significant decisions or discoveries
- **At task end**: call `retain` (hindsight server) with a summary of what was accomplished

### MCP server entry

The installer writes the following to `.roo/mcp.json`:

```json
{
  "mcpServers": {
    "hindsight": {
      "url": "http://localhost:8888/mcp",
      "timeout": 10000,
      "alwaysAllow": ["recall", "retain"]
    }
  }
}
```

`alwaysAllow` means Roo won't prompt for approval on each call — memory operations happen silently.

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--api-url` | `http://localhost:8888` | Hindsight API base URL |
| `--project-dir` | current directory | Project to install into |
| `--global` | off | Write to `~/.roo/` instead of `.roo/` |

To add an API key for Hindsight Cloud, edit `.roo/mcp.json` and add a `headers` field:

```json
{
  "mcpServers": {
    "hindsight": {
      "url": "https://api.hindsight.vectorize.io/mcp",
      "timeout": 10000,
      "alwaysAllow": ["recall", "retain"],
      "headers": {
        "Authorization": "Bearer hsk_your_token_here"
      }
    }
  }
}
```

## Core Files

| File | Description |
|------|-------------|
| `seed_memory.py` | Seeds sample developer facts for demo purposes |
| `requirements.txt` | Python dependencies for seed script |
| `install.py` | Installer — writes `.roo/mcp.json` and copies rules file |
| `rules/hindsight-memory.md` | Rules file injected into every Roo system prompt |

## Common Issues

**Hindsight not showing in MCP Servers**

Re-run the installer and restart VS Code. Check that `.roo/mcp.json` exists in your project root.

**No memories recalled on the first session**

Recall only returns results after something has been retained. Either:
- Run `seed_memory.py` to pre-populate facts, or
- Complete one task (Roo retains at task end) and then start a new task

**recall not firing automatically**

Check that `.roo/rules/hindsight-memory.md` exists. If it's missing, re-run `python install.py`.

**API key not working**

Add the `Authorization` header to the MCP server entry in `.roo/mcp.json` as shown in the Configuration section above.

## Built With

- [Roo Code](https://github.com/RooVetGit/Roo-Code) — agentic AI coding assistant for VS Code
- [Hindsight](https://hindsight.vectorize.io) — long-term memory for AI agents
- [Hindsight Roo Code integration](https://github.com/vectorize-io/hindsight/tree/main/hindsight-integrations/roo-code) — installer and rules file
