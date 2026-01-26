# Hindsight Cookbook

A collection of example applications demonstrating how to integrate and use [Hindsight](https://github.com/vectorize-io/hindsight).

## Examples

### [OpenAI Fitness Coach](./openai-fitness-coach)

A fitness coach example demonstrating how to use **OpenAI Agents** with **Hindsight as a memory backend**. Shows:
- OpenAI Assistants handling conversation logic
- Hindsight providing memory storage & retrieval via function calling
- Streaming responses and preference learning
- Real-world integration pattern for adding memory to AI agents

```bash
cd openai-fitness-coach
export OPENAI_API_KEY=your_key
python demo_conversational.py
```

### [LiteLLM Memory Demo](./hindsight-litellm-demo)

An interactive side-by-side comparison of three memory approaches:
- No Memory (baseline)
- Full Conversation History (truncated)
- Hindsight Memory (semantic recall)

```bash
cd hindsight-litellm-demo
./run.sh
```

### [Tool Learning Demo](./hindsight-tool-learning-demo)

An interactive Streamlit demo showing how Hindsight helps LLMs learn which tool to use when tool names are ambiguous. Demonstrates:
- Side-by-side comparison: routing with and without memory
- Learning from feedback to improve tool selection accuracy
- Customer service routing scenario with vague tool names

```bash
cd hindsight-tool-learning-demo
./run.sh
```

### [Stance Tracker](./stancetracker)

A web application for tracking political stances and positions using AI-powered memory. Features:
- Track and recall political positions from conversations
- File-based memory storage
- Real-time stance extraction and organization
- Integration with Hindsight for semantic memory

```bash
cd stancetracker
./scripts/setup.sh
npm run dev
```

### [Conversational AI with Per-User Memory](./chat-memory)
Simple chatbot that remembers past conversations on a per user basis:
- Track and recall memories from past conversations
- Creates a memory bank per user
- Integration with Hindsight for semantic memory

Start Hindsight using docker with OpenAI or your [preferred LLM provider](https://hindsight.vectorize.io/developer/models):

```bash
export OPENAI_API_KEY=your-key

docker run --rm -it --pull always -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  -e HINDSIGHT_API_LLM_MODEL=o3-mini \
  -v $HOME/.hindsight-docker:/home/hindsight/.pg0 \
  ghcr.io/vectorize-io/hindsight:latest
```


Then: 
```bash
cd chat-memory
npm i
npm run dev
```

## Quick Start Demos

The [demos](./demos) directory contains ready-to-run example applications showcasing Hindsight's memory capabilities:

| Demo | Description |
|------|-------------|
| Movie Recommendation | Personalized movie recommender that learns your tastes |
| Fitness Tracker | Fitness coach with workout and diet memory |
| Study Buddy | Study assistant with spaced repetition |
| Personal Assistant | General-purpose assistant with long-term memory |
| Healthcare Assistant | Health chatbot demo |
| Personalized Search | Context-aware search agent |

Each demo includes both a Python script and Jupyter notebook. See the [demos README](./demos/README.md) for setup instructions.

## Notebooks

Interactive Jupyter notebooks demonstrating Hindsight features:


### Prerequisites

1. **Start Hindsight** (via Docker):

```bash
export OPENAI_API_KEY=your-key

docker run --rm -it --pull always -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  -e HINDSIGHT_API_LLM_MODEL=o3-mini \
  -v $HOME/.hindsight-docker:/home/hindsight/.pg0 \
  ghcr.io/vectorize-io/hindsight:latest
```

- API: http://localhost:8888
- UI: http://localhost:9999

2. Run the notebooks

| Notebook | Description |
|----------|-------------|
| [01-quickstart.ipynb](notebooks/01-quickstart.ipynb) | Basic operations: retain, recall, and reflect |
| [02-per-user-memory.ipynb](notebooks/02-per-user-memory.ipynb) | Pattern for giving each user their own memory bank |
| [03-support-agent-shared-knowledge.ipynb](notebooks/03-support-agent-shared-knowledge.ipynb) | Multi-bank architecture for support agents with shared docs |
| [04-litellm-memory-demo.ipynb](notebooks/04-litellm-memory-demo.ipynb) | Automatic memory with LiteLLM callbacks |
| [05-tool-learning-demo.ipynb](notebooks/05-tool-learning-demo.ipynb) | Learning correct tool selection through memory |

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

MIT
