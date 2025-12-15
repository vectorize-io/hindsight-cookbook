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
| [04-typescript-client.md](notebooks/04-typescript-client.md) | TypeScript/Node.js client examples |
| [05-openai-integration.ipynb](notebooks/05-openai-integration.ipynb) | Drop-in OpenAI wrapper with automatic memory |

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

MIT
