---
description: "OpenClaw messaging gateway with automatic persistent memory via Hindsight"
tags: { sdk: "@vectorize-io/hindsight-openclaw", topic: "Agents" }
---

# OpenClaw + Hindsight Memory

Give your OpenClaw agents persistent memory across Slack, Telegram, Discord, and every other channel they live in. The `@vectorize-io/hindsight-openclaw` plugin automatically captures every conversation and recalls relevant context before each agent response — no changes to your agents or prompts required.

## What This Demonstrates

- **Automatic retention** — every conversation is stored after each turn without the agent deciding what to save
- **Automatic recall** — relevant memories are injected into context before every agent response
- **Three backends** — Hindsight Cloud (managed), embedded local daemon, or self-hosted API
- **Per-user and per-channel memory isolation** — configurable via `dynamicBankGranularity`
- **Memory inspection** — browse and query stored memories from the terminal

## Architecture

```
Slack / Telegram / Discord / any channel
        │
        ▼
   OpenClaw Gateway
        │
   hindsight-openclaw plugin
        │
        ├─ Before each response ──→ auto-recall ──→ inject relevant memories
        │                                                    │
        │                                             Hindsight API
        │                                                    │
        └─ After each response  ──→ auto-retain ──→ store conversation
```

The LLM you configure for memory extraction runs separately from your agent's LLM. Memory extraction happens in the background and never blocks the agent response.

## Prerequisites

1. **OpenClaw installed** with at least one messaging channel configured (Slack, Telegram, Discord, etc.)

2. **A Hindsight backend** — pick one:

   | Option | Setup |
   |--------|-------|
   | **Hindsight Cloud** (easiest) | [Sign up](https://ui.hindsight.vectorize.io/signup) for a free `hsk_...` token |
   | **Embedded daemon** (local, no extra services) | Just an LLM API key — the daemon starts automatically |
   | **Self-hosted API** | Run Hindsight via Docker (see below) |

   For the self-hosted option:
   ```bash
   export OPENAI_API_KEY=your-key

   docker run --rm -it --pull always -p 8888:8888 -p 9999:9999 \
     -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
     -v $HOME/.hindsight-docker:/home/hindsight/.pg0 \
     ghcr.io/vectorize-io/hindsight:latest
   ```

## Quick Start

**Step 1: Install the plugin**

```bash
openclaw plugins install @vectorize-io/hindsight-openclaw
```

**Step 2: Run the setup wizard**

Pick the path that matches your backend:

```bash
# Hindsight Cloud (paste your hsk_... token when prompted)
npx --package @vectorize-io/hindsight-openclaw hindsight-openclaw-setup \
    --mode cloud --token hsk_your_token

# Embedded daemon with OpenAI
npx --package @vectorize-io/hindsight-openclaw hindsight-openclaw-setup \
    --mode embedded --provider openai --api-key sk-...

# Embedded daemon with Claude Code (no separate API key needed)
npx --package @vectorize-io/hindsight-openclaw hindsight-openclaw-setup \
    --mode embedded --provider claude-code

# Self-hosted API
npx --package @vectorize-io/hindsight-openclaw hindsight-openclaw-setup \
    --mode api --api-url http://localhost:8888
```

Or run the interactive wizard (no flags) and it will prompt you:

```bash
npx --package @vectorize-io/hindsight-openclaw hindsight-openclaw-setup
```

You can also use one of the example config files in `configs/` directly:

```bash
cp configs/openclaw.cloud.example.json ~/.openclaw/openclaw.json
# edit to fill in your token
```

**Step 3: Start OpenClaw**

```bash
openclaw gateway
```

You should see the plugin confirm the backend on startup:

```
[Hindsight] ✓ Using provider: openai, model: gpt-4o-mini
```
or
```
[Hindsight] External API mode enabled: https://api.hindsight.vectorize.io
[Hindsight] External API health check passed
```

## Try It Out

Send a few messages through any connected channel, then start a new session:

**Session 1 (Slack DM):**
```
You: I'm building a TypeScript API and I prefer strict type checking over convenience
OpenClaw: Got it — I'll keep that in mind. What are you working on first?
```

**Session 2 (same or different channel):**
```
You: What do you know about my project preferences?
OpenClaw: You're building a TypeScript API and you prefer strict type checking over convenience.
```

That's it. No tool calls, no prompting the agent to "remember" anything — Hindsight extracted the fact and recalled it automatically.

## How It Works

**Auto-retain:** After each agent turn, the plugin sends the conversation transcript to Hindsight. The memory engine extracts discrete facts, entities, and relationships and stores them in a bank keyed to the conversation context.

**Auto-recall:** Before each agent response, the plugin queries Hindsight using the current user message. Relevant memories are prepended (or appended, or injected as a user message) into the agent's context.

**Feedback loop prevention:** The plugin automatically strips `<hindsight_memories>` tags before retaining, so recalled memories are never re-extracted as new facts.

The minimal config that enables both behaviors:

```json
{
  "plugins": {
    "entries": {
      "hindsight-openclaw": {
        "enabled": true,
        "config": {
          "autoRecall": true,
          "autoRetain": true,
          "dynamicBankGranularity": ["agent", "user"]
        }
      }
    }
  }
}
```

## Configuration Reference

| Key | Default | Description |
|-----|---------|-------------|
| `llmProvider` | — | LLM for memory extraction: `openai`, `anthropic`, `gemini`, `groq`, `ollama`, `claude-code`, `openai-codex` |
| `llmApiKey` | — | API key for the extraction LLM (omit for `claude-code` / `openai-codex`) |
| `llmModel` | provider default | Model override (e.g. `gpt-4o-mini`) |
| `hindsightApiUrl` | — | URL for Cloud or self-hosted Hindsight API |
| `hindsightApiToken` | — | Auth token for Hindsight Cloud |
| `autoRecall` | `true` | Inject memories before each agent response |
| `autoRetain` | `true` | Store conversations after each turn |
| `dynamicBankId` | `true` | Derive bank ID from conversation context |
| `dynamicBankGranularity` | `["agent","channel","user"]` | Which context fields determine the bank ID |
| `bankId` | — | Fixed bank name (when `dynamicBankId` is `false`) |
| `bankIdPrefix` | — | Prefix added to all dynamic bank IDs (e.g. `"prod"`) |
| `recallBudget` | `"mid"` | Retrieval effort: `"low"`, `"mid"`, or `"high"` |
| `recallMaxTokens` | `1024` | Max tokens for injected memories per turn |
| `recallInjectionPosition` | `"prepend"` | Where memories land: `"prepend"`, `"append"`, or `"user"` |

## Configuration Patterns

### Default: Per-agent + Per-channel + Per-user (the default)

The default `dynamicBankGranularity` of `["agent", "channel", "user"]` means each unique combination of bot, conversation, and person gets its own isolated memory store. A Slack DM and a Telegram group chat involving the same user have separate memories.

No config change needed — this is what the setup wizard configures.

### Shared bank (all users share one brain)

All conversations feed into one memory store — useful for a team bot that should remember decisions made by anyone:

```json
{
  "config": {
    "dynamicBankId": false,
    "bankId": "my-team-bot"
  }
}
```

See `configs/openclaw.external.example.json` for a full example of this pattern.

### Per-user memory (shared across all channels)

The same user gets the same memories whether they DM the bot or talk to it in a group channel:

```json
{
  "config": {
    "dynamicBankGranularity": ["user"]
  }
}
```

### Per-agent team brain

All users talking to the same agent share one memory pool — good for a project-scoped assistant:

```json
{
  "config": {
    "dynamicBankGranularity": ["agent"]
  }
}
```

### Namespaced environments

Prefix bank IDs to separate staging and production memories sharing the same backend:

```json
{
  "config": {
    "bankIdPrefix": "prod"
  }
}
```

## Inspect Memory

Check what the agent has stored:

```bash
# Is the embedded daemon running?
uvx hindsight-embed@latest -p openclaw daemon status

# Search stored memories
uvx hindsight-embed@latest -p openclaw memory recall openclaw "user preferences"

# Browse the web UI (embedded mode only)
uvx hindsight-embed@latest -p openclaw ui
```

Or use the included helper:

```bash
./scripts/inspect-memory.sh
```

Check gateway logs for memory operations:

```bash
tail -f /tmp/openclaw/openclaw-*.log | grep Hindsight

# After conversations you should see:
# [Hindsight] Retained X messages for session ...
# [Hindsight] Auto-recall: Injecting X memories
```

## Core Files

| File | Description |
|------|-------------|
| `configs/openclaw.embedded.example.json` | Full config for embedded daemon mode (OpenAI) |
| `configs/openclaw.cloud.example.json` | Config for Hindsight Cloud |
| `configs/openclaw.external.example.json` | Config for self-hosted Hindsight API |
| `scripts/setup.sh` | Interactive setup wrapper around `hindsight-openclaw-setup` |
| `scripts/inspect-memory.sh` | Quick memory inspection via CLI |

## Common Issues

**Plugin not found after install**

```bash
openclaw plugins list | grep hindsight
# If missing, reinstall:
openclaw plugins install @vectorize-io/hindsight-openclaw
```

**Connection refused / health check failed**

For embedded mode, the daemon starts automatically on `openclaw gateway`. If it fails, check the profile log:
```bash
tail -f ~/.hindsight/profiles/openclaw.log
```

For Cloud or external API mode, verify your token and URL are correct:
```bash
openclaw config get plugins.entries.hindsight-openclaw.config.hindsightApiUrl
```

**No memories recalled in the first session**

Expected — there's nothing stored yet. Send a few messages, then start a new session. Memory extraction runs asynchronously after each turn, so it may take a moment after the conversation ends.

**LLM API key not set (embedded mode)**

The plugin no longer reads `OPENAI_API_KEY` from the environment automatically. Set it explicitly:

```bash
openclaw config set plugins.entries.hindsight-openclaw.config.llmProvider openai
openclaw config set plugins.entries.hindsight-openclaw.config.llmApiKey \
    --ref-source env --ref-provider default --ref-id OPENAI_API_KEY
```

Or use a provider that needs no key: `--provider claude-code` or `--provider openai-codex`.

**First launch takes several minutes**

On the first run, `hindsight-embed` downloads Python packages including sentence-transformers (~3 GB). Subsequent launches use the cached packages. The plugin auto-retries during this window.

## Built With

- [OpenClaw](https://openclaw.ai) — self-hosted AI gateway for messaging platforms
- [@vectorize-io/hindsight-openclaw](https://www.npmjs.com/package/@vectorize-io/hindsight-openclaw) — Hindsight memory plugin for OpenClaw
- [Hindsight](https://vectorize.io/hindsight) — long-term memory for AI agents
