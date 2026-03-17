---
description: "Hermes Agent with persistent long-term memory via Hindsight"
tags: { sdk: "hindsight-hermes", topic: "Agents" }
---

# Hermes Agent + Hindsight Memory

Give your [Hermes Agent](https://github.com/NousResearch/hermes-agent) persistent long-term memory. Chat across sessions and the agent remembers what you told it.

## What This Demonstrates

- **Plugin-based memory** for Hermes via `hindsight-hermes`
- **Persistent memory across sessions** — close Hermes, reopen it, memories are still there
- **Three memory operations** — retain (store), recall (search), reflect (synthesize)
- **Standalone demo mode** — test memory operations without running Hermes

## Architecture

```
Session 1: "Remember my favourite language is Rust"
    │
    ├─ Hermes calls hindsight_retain ──► Hindsight API
    │                                      ├── fact extraction
    │                                      ├── entity resolution
    │                                      └── knowledge graph indexing
    │
Session 2: "What do you know about my preferences?"
    │
    ├─ Hermes calls hindsight_recall ──► Hindsight API
    │                                      ├── semantic search
    │                                      ├── BM25 keyword matching
    │                                      ├── entity graph traversal
    │                                      └── cross-encoder reranking
    │
    └─ Agent responds with recalled context
```

## Prerequisites

1. **Hindsight running**

   ```bash
   export OPENAI_API_KEY=your-key

   docker run --rm -it --pull always -p 8888:8888 -p 9999:9999 \
     -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
     -e HINDSIGHT_API_LLM_MODEL=o3-mini \
     -v $HOME/.hindsight-docker:/home/hindsight/.pg0 \
     ghcr.io/vectorize-io/hindsight:latest
   ```

2. **Hermes Agent installed** ([setup guide](https://github.com/NousResearch/hermes-agent))

   ```bash
   git clone https://github.com/NousResearch/hermes-agent.git
   cd hermes-agent
   git submodule update --init mini-swe-agent
   uv venv .venv --python 3.11
   source .venv/bin/activate
   uv pip install -e ".[all,dev]"
   uv pip install -e "./mini-swe-agent"
   ```

3. **Install hindsight-hermes into the Hermes venv**

   ```bash
   # From within the Hermes venv
   pip install -r requirements.txt
   ```

   > **Note:** `hindsight-hermes` is not yet on PyPI — it is installed directly from the
   > [Hindsight repo](https://github.com/vectorize-io/hindsight/tree/main/hindsight-integrations/hermes) via git.

4. **Disable Hermes's built-in memory**

   ```bash
   hermes tools disable memory
   ```

   This prevents the LLM from using the built-in file-based memory instead of Hindsight.

## Quick Start

### Option A: Full Hermes Agent

```bash
# Set environment variables
export HINDSIGHT_API_URL=http://localhost:8888
export HINDSIGHT_BANK_ID=hermes-assistant
export OPENAI_API_KEY=your-key

# Launch Hermes with Hindsight memory
hermes

# In the chat, try:
#   "Remember that my favourite programming language is Rust"
#   "What do you know about my preferences?"
#   "Based on what you know about me, suggest a project"
```

Verify the tools loaded by typing `/tools` — look for the `[hindsight]` toolset.

### Option B: Standalone Demo (no Hermes needed)

```bash
# Run the demo to see retain/recall/reflect in action
python personal_assistant.py --demo

# Interactive mode with direct commands
python personal_assistant.py

# Single recall query
python personal_assistant.py "programming preferences"

# Reset memory
python personal_assistant.py --reset
```

## How It Works

### 1. Plugin Auto-Registration

When you `pip install hindsight-hermes`, it declares an entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
hindsight = "hindsight_hermes"
```

On startup, Hermes discovers the plugin and calls `register(ctx)`, which registers three tools.

### 2. The Three Tools

**hindsight_retain** — Store memories:

```python
# What happens when Hermes calls hindsight_retain:
client.retain(bank_id="hermes-assistant", content="User's favourite language is Rust")
# Hindsight extracts facts, resolves entities, builds knowledge graph
```

**hindsight_recall** — Search memories:

```python
# What happens when Hermes calls hindsight_recall:
response = client.recall(bank_id="hermes-assistant", query="programming preferences", budget="mid")
# Returns relevant facts via semantic + BM25 + graph search, reranked
```

**hindsight_reflect** — Synthesize across memories:

```python
# What happens when Hermes calls hindsight_reflect:
response = client.reflect(bank_id="hermes-assistant", query="suggest a project based on my preferences")
# Reasons across all stored memories and returns a synthesized answer
```

### 3. Bank Auto-Creation

The plugin auto-creates the memory bank on first use. The bank ID comes from the `HINDSIGHT_BANK_ID` environment variable.

## Core Files

| File | Description |
|------|-------------|
| `personal_assistant.py` | Standalone demo with retain/recall/reflect + interactive mode |
| `requirements.txt` | Python dependencies |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `HINDSIGHT_API_URL` | `http://localhost:8888` | Hindsight API URL |
| `HINDSIGHT_BANK_ID` | `hermes-assistant` | Memory bank identifier |
| `HINDSIGHT_API_KEY` | — | API key (only for Hindsight Cloud) |
| `HINDSIGHT_BUDGET` | `mid` | Recall budget: low/mid/high |

## Common Issues

**Tools not showing in `/tools`**
- Make sure `hindsight-hermes` is installed in the **same venv** as Hermes
- Verify: `python -c "import importlib.metadata; print(list(importlib.metadata.entry_points(group='hermes_agent.plugins')))"`

**Hermes uses built-in memory instead of Hindsight**
```bash
hermes tools disable memory
```

**"Connection refused"**
- Make sure Hindsight is running on `localhost:8888`

**"No module named 'hindsight_hermes'"**
```bash
pip install -r requirements.txt
```

---

**Built with:**
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) - Self-improving AI agent with plugin system
- [hindsight-hermes](https://github.com/vectorize-io/hindsight/tree/main/hindsight-integrations/hermes) - Hindsight memory plugin for Hermes
- [Hindsight](https://github.com/vectorize-io/hindsight) - Long-term memory for AI agents
