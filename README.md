# Hindsight Cookbook

A collection of example applications demonstrating how to integrate and use [Hindsight](https://github.com/vectorize-io/hindsight).

## Table of Contents

- [Getting Started](#getting-started)
- [Examples](#examples)
- [Contributing](#contributing)
- [License](#license)

## Getting Started

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

2. **Install the Python client**:

```bash
pip install hindsight-client -U
```

Or for Node.js:

```bash
npm install @vectorize-io/hindsight-client
```

Each example is self-contained with its own setup instructions.

## Examples

### Notebooks

Interactive Jupyter notebooks demonstrating Hindsight features:

| Notebook | Description |
|----------|-------------|
| [01-quickstart.ipynb](notebooks/01-quickstart.ipynb) | Basic operations: retain, recall, and reflect |
| [02-per-user-memory.ipynb](notebooks/02-per-user-memory.ipynb) | Pattern for giving each user their own memory bank |
| [03-support-agent-shared-knowledge.ipynb](notebooks/03-support-agent-shared-knowledge.ipynb) | Multi-bank architecture for support agents with shared docs |
| [04-typescript-client.md](notebooks/04-typescript-client.md) | TypeScript/Node.js client examples |
| [05-openai-integration.ipynb](notebooks/05-openai-integration.ipynb) | Drop-in OpenAI wrapper with automatic memory |

### Demos

| Demo | Description |
|------|-------------|
| [hindsight-tool-learning-demo](hindsight-tool-learning-demo/) | Interactive demo comparing memory approaches |

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

MIT
