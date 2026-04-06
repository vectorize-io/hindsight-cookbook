---
description: "Give Cursor 3 persistent memory across sessions using the Hindsight Cursor plugin"
tags: { sdk: "hindsight-cursor", topic: "Agents" }
---

# Cursor Memory

Give [Cursor](https://cursor.com) persistent memory across sessions using the Hindsight Cursor plugin. The plugin recalls relevant context before each prompt and retains conversation transcripts after each task, so Cursor 3 agents can pick up where they left off.

## What This Demonstrates

- **Automatic recall** — Hindsight injects relevant memories before each Cursor prompt via `beforeSubmitPrompt`
- **Automatic retain** — Cursor task transcripts are stored to Hindsight after each task via `stop`
- **Cross-session continuity** — Cursor remembers project context, preferences, and decisions across separate chats
- **Cursor 3 workflow fit** — works with the new Agents Window, rules, and skills model
- **Per-project or per-session isolation** — optional dynamic bank IDs keep memory scoped however you want

## Prerequisites

1. **Cursor 3** with plugin support enabled
2. **Python 3.9+**
   ```bash
   python3 --version
   ```
3. **A running Hindsight API**
   - Local: `http://localhost:8888`
   - Or Hindsight Cloud / self-hosted API

## Quick Start

### 1. Install the Cursor plugin into a test project

```bash
mkdir -p /path/to/your-project/.cursor-plugin
cp -r /path/to/hindsight/hindsight-integrations/cursor /path/to/your-project/.cursor-plugin/hindsight-memory
```

> If Cursor is already open, **fully quit and reopen it** after adding the plugin. Plugins load at startup.

### 2. Configure Hindsight

Create `~/.hindsight/cursor.json`:

**Option A — Hindsight Cloud** (no local server needed):
```json
{
  "hindsightApiUrl": "https://api.hindsight.vectorize.io",
  "hindsightApiToken": "YOUR_HINDSIGHT_API_TOKEN",
  "bankId": "cursor"
}
```

Sign up at [Hindsight Cloud](https://ui.hindsight.vectorize.io/signup) to get a token.

**Option B — Local server:**
```json
{
  "hindsightApiUrl": "http://localhost:8888",
  "bankId": "cursor"
}
```

While testing, it helps to retain every task:

```json
{
  "hindsightApiUrl": "http://localhost:8888",
  "bankId": "cursor",
  "retainEveryNTurns": 1
}
```

### 3. Seed the demo bank

```bash
uv run --with hindsight-client python seed_memory.py --reset
```

### 4. Verify the seed data

```bash
uv run --with hindsight-client python verify_memory.py
```

### 5. Open Cursor 3

Open the target project in Cursor, then run:

```text
Cmd+Shift+P -> Agents Window
```

Ask Cursor questions like:

- `What testing framework do I prefer for Python work?`
- `What stack is this project using?`
- `What coding style do I usually prefer?`

The plugin injects the matching memories before the prompt reaches the model.

## Files

| File | Description |
|------|-------------|
| `seed_memory.py` | Seeds sample developer facts for the Cursor memory demo |
| `verify_memory.py` | Queries Hindsight directly to verify the seed and recall flow |
| `requirements.txt` | Optional dependencies if you prefer `pip install -r requirements.txt` |

## Notes

- Use `dynamicBankId: true` with `["agent", "project"]` to isolate memory per repository.
- Use `["session"]` if you want one bank per Cursor conversation.
- Cursor also supports Hindsight via MCP in `.cursor/mcp.json`, but the plugin path is the most automatic workflow.
