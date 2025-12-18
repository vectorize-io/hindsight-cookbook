# Delivery Agent Demo

A retro-style demo showcasing how AI agents learn to navigate using **Hindsight memory**.

```
┌─────────────────────────────────────────────────────────┐
│  F5  │ SkyView Marketing │ ║ │ CloudNine Consulting │  │
│──────┼───────────────────┼─║─┼──────────────────────┼──│
│  F4  │ FinanceHub Capital│ ║ │ MedTech Solutions    │  │
│──────┼───────────────────┼─║─┼──────────────────────┼──│
│  F3  │ Acme Corporation  │ ║ │ Creative Designs Co  │  │
│──────┼───────────────────┼─║─┼──────────────────────┼──│
│  F2  │ TechStart Labs    │ ║ │ Legal Eagles LLP     │  │
│──────┼───────────────────┼─║─┼──────────────────────┼──│
│  F1  │ 🚶📦 Lobby        │ ║ │ BuildingOps Inc      │  │
└─────────────────────────────────────────────────────────┘
```

## The Demo

An LLM-powered delivery agent must deliver packages to employees in a 5-floor office building. The agent:

1. **Starts with no knowledge** of the building layout
2. **Explores** to find businesses and employees
3. **Learns** from each delivery experience via Hindsight
4. **Improves** over time - deliveries get faster as memory builds

## What It Demonstrates

### Without Memory (First Deliveries)
- Agent wanders floor-to-floor checking each business
- Takes many steps to find the destination
- No efficiency improvement over time

### With Hindsight Memory
- Agent recalls previous delivery experiences
- Learns where businesses and employees are located
- Directly navigates to known destinations
- Steps per delivery decrease dramatically

## Quick Start

```bash
# 1. Make sure Hindsight is running
docker run -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  -e HINDSIGHT_API_LLM_MODEL=gpt-4o-mini \
  ghcr.io/vectorize-io/hindsight:latest

# 2. Set your OpenAI API key
export OPENAI_API_KEY=sk-...

# 3. Run the demo
cd delivery-agent-demo
./run.sh
```

Open http://localhost:8503 in your browser.

## How It Works

### Agent Tools

The agent has access to these tools:

| Tool | Description |
|------|-------------|
| `go_up` | Move up one floor |
| `go_down` | Move down one floor |
| `go_to_front` | Go to front side of floor |
| `go_to_back` | Go to back side of floor |
| `look_at_business` | See which business is here |
| `get_employee_list` | See who works here |
| `deliver_package` | Attempt delivery |

### Memory Flow

```
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│ New Package  │────▶│ Recall Past │────▶│ Navigate     │
│ Assignment   │     │ Deliveries  │     │ (w/ context) │
└──────────────┘     └─────────────┘     └──────┬───────┘
                                                │
                                                ▼
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│ Learning     │◀────│ Store New   │◀────│ Delivery     │
│ Improves     │     │ Experience  │     │ Complete     │
└──────────────┘     └─────────────┘     └──────────────┘
```

### What Gets Stored

After each delivery, Hindsight stores:
- Who was delivered to
- Which business they work at
- Floor and side location
- Number of steps taken

Example memory:
> "Successfully delivered package to Alex Chen. Alex Chen works at TechStart Labs which is located on Floor 2, front side. Delivery took 8 steps."

### What Gets Recalled

Before each delivery, the agent queries Hindsight:
- "Where does [recipient] work?"
- "Where is [business name] located?"

If memories exist, the agent receives context like:
> "Based on your previous delivery experiences: TechStart Labs is on Floor 2, front side."

## Metrics

The demo tracks:

| Metric | Description |
|--------|-------------|
| **Deliveries** | Total successful deliveries |
| **Total Steps** | Cumulative navigation steps |
| **Avg Steps/Delivery** | Efficiency metric (should decrease!) |
| **Memories Stored** | Number of experiences in Hindsight |
| **Learning Curve** | Graph showing steps over time |

## Files

```
delivery-agent-demo/
├── app.py              # Streamlit UI with retro sprites
├── agent.py            # LLM-powered delivery agent
├── agent_tools.py      # Navigation tools for the agent
├── building.py         # Building simulation
├── memory.py           # Hindsight integration
├── requirements.txt    # Dependencies
├── run.sh             # Launch script
├── .env.example       # Environment template
└── README.md          # This file
```

## Configuration

Edit `.env` to customize:

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional
HINDSIGHT_API_URL=http://localhost:8888
LLM_MODEL=gpt-4o-mini  # or gpt-4o, etc.
```

## Tips for Demoing

1. **Start fresh**: Click "Clear Memory" to reset
2. **First delivery**: Watch the agent explore randomly
3. **Same recipient**: Deliver to the same person again - much faster!
4. **Different people, same business**: Shows building layout learning
5. **Toggle business name**: See how additional info affects navigation

## Troubleshooting

**"Could not connect to Hindsight"**
- Make sure Hindsight is running on port 8888
- Check `HINDSIGHT_API_URL` in your `.env`

**Slow responses**
- Try a faster model like `gpt-4o-mini`
- Check your OpenAI API quota

**Agent gets stuck**
- Click "New Delivery" to start fresh
- The agent has a 50-step limit per delivery
