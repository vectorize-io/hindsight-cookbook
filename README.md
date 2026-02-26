# Hindsight Cookbook

A collection of example applications and notebooks demonstrating how to integrate and use [Hindsight](https://github.com/vectorize-io/hindsight).

## Applications

Full-featured example applications demonstrating Hindsight integration patterns:

- **[chat-memory](./applications/chat-memory)** - Conversational AI with per-user memory
- **[deliveryman-demo](./applications/deliveryman-demo)** - Interactive delivery agent with memory-based navigation
- **[hindsight-litellm-demo](./applications/hindsight-litellm-demo)** - Side-by-side comparison of memory approaches
- **[hindsight-tool-learning-demo](./applications/hindsight-tool-learning-demo)** - Learning tool selection through memory
- **[openai-fitness-coach](./applications/openai-fitness-coach)** - Fitness coach with OpenAI Agents and Hindsight memory
- **[sanity-blog-memory](./applications/sanity-blog-memory)** - Syncing Sanity CMS content to Hindsight
- **[chat-sdk-multi-platform](./applications/chat-sdk-multi-platform)** - Cross-platform Slack + Discord bot with shared memory (Vercel Chat SDK)
- **[stancetracker](./applications/stancetracker)** - Track political stances using AI-powered memory

## Notebooks

Interactive Jupyter notebooks demonstrating Hindsight features:

### Core Tutorials

- **[01-quickstart.ipynb](./notebooks/01-quickstart.ipynb)** - Basic operations: retain, recall, and reflect
- **[02-per-user-memory.ipynb](./notebooks/02-per-user-memory.ipynb)** - Pattern for per-user memory banks
- **[03-support-agent-shared-knowledge.ipynb](./notebooks/03-support-agent-shared-knowledge.ipynb)** - Multi-bank architecture for support agents
- **[04-litellm-memory-demo.ipynb](./notebooks/04-litellm-memory-demo.ipynb)** - Automatic memory with LiteLLM callbacks
- **[05-tool-learning-demo.ipynb](./notebooks/05-tool-learning-demo.ipynb)** - Learning tool selection through memory

### Quick Demos

- **[fitness_tracker.ipynb](./notebooks/fitness_tracker.ipynb)** - Fitness coach with workout and diet memory
- **[healthcare_assistant.ipynb](./notebooks/healthcare_assistant.ipynb)** - Health chatbot demo
- **[movie_recommendation.ipynb](./notebooks/movie_recommendation.ipynb)** - Personalized movie recommender
- **[personal_assistant.ipynb](./notebooks/personal_assistant.ipynb)** - General-purpose assistant with long-term memory
- **[personalized_search.ipynb](./notebooks/personalized_search.ipynb)** - Context-aware search agent
- **[study_buddy.ipynb](./notebooks/study_buddy.ipynb)** - Study assistant with spaced repetition

## Getting Started

### Prerequisites

Start Hindsight using Docker:

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

See [Hindsight documentation](https://hindsight.vectorize.io/developer/models) for other LLM providers.

### Running Notebooks

Each notebook can be run independently. Install dependencies:

```bash
cd notebooks
pip install -r requirements.txt
jupyter notebook
```

### Running Applications

Each application has its own setup instructions in its README.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

MIT
