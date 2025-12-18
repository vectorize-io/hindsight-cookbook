# Quick Start - Delivery Agent Demo

Get running in 3 minutes!

## Prerequisites

- Python 3.9+
- OpenAI API key
- Hindsight running (see below)

## 1. Start Hindsight (if not running)

```bash
docker run -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  ghcr.io/vectorize-io/hindsight:latest
```

## 2. Configure

```bash
cd delivery-agent-demo
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## 3. Run

```bash
./run.sh
```

## 4. Open

Navigate to http://localhost:8503

## 5. Demo

1. Click **"New Delivery"** - watch the agent explore
2. Click again (same recipient) - see it go directly!
3. Watch the **Learning Curve** graph trend downward
