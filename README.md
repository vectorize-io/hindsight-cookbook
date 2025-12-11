# Hindsight Cookbook

A collection of example applications demonstrating how to integrate and use [Hindsight](https://github.com/vectorize-io/hindsight).

## Table of Contents

- [Getting Started](#getting-started)
- [Examples](#examples)
- [Contributing](#contributing)
- [License](#license)

## Getting Started

Each example is self-contained in its own directory with its own README and setup instructions.

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

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

MIT
