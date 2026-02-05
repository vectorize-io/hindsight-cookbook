# Hindsight AI SDK - Personal Chef

A personal food assistant that learns your tastes and dietary needs over time, built with the [Hindsight AI SDK](https://www.npmjs.com/package/@vectorize-io/hindsight-ai-sdk).

## What is Hindsight?

**Hindsight** is an AI memory system that lets your applications remember user preferences, learn from interactions, and provide personalized experiences across conversations. Instead of starting fresh every time, the AI builds up a persistent understanding of each user.

In this demo, Hindsight remembers:
- Your food preferences and dietary restrictions
- Meals you've eaten and enjoyed
- Foods you dislike or want to avoid
- Your health goals and eating patterns

## How It Works

1. **Set Your Preferences** - Tell the AI about your cuisine preferences, dietary restrictions, and health goals
2. **Get Personalized Suggestions** - The AI generates recipes tailored to your tastes and needs
3. **Log Your Meals** - Track what you ate, what you cooked, or what you'd never eat
4. **Track Your Health** - The AI analyzes your eating patterns and provides a health score

## Key Features

This demo showcases three core Hindsight capabilities:

- **`retain`** - Stores your preferences, meals, and dislikes in memory
- **`recall`** - Searches your memory to personalize suggestions
- **`reflect`** - Analyzes patterns in your eating habits to generate insights

## Using Hindsight with AI SDK

This demo uses the Hindsight AI SDK with [Vercel AI SDK v6](https://sdk.vercel.ai/docs):

```typescript
import { createHindsightTools } from '@anthropic/hindsight-ai-sdk';

// Create Hindsight tools
const tools = createHindsightTools({ client: hindsightClient });

// Use with AI SDK's generateText
const result = await generateText({
  model: llmModel,
  tools: {
    recall: tools.recall,
    reflect: tools.reflect,
  },
  toolChoice: 'auto',
  prompt: 'What recipes would you recommend based on my preferences?',
});
```

The AI automatically uses Hindsight tools to remember your preferences and personalize responses.

## Running the Demo

```bash
npm install
npm run dev
```

**Requirements:**
- A running Hindsight server at `http://localhost:8888` (or set `HINDSIGHT_URL` environment variable)
- Node.js 18+

## Learn More

- [Hindsight AI SDK on npm](https://www.npmjs.com/package/@vectorize-io/hindsight-ai-sdk)
- [AI SDK Documentation](https://sdk.vercel.ai/docs)
