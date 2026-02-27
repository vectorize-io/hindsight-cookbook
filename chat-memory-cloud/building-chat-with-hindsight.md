# Building a Chat System with Persistent Memory Using Hindsight

Most AI chat applications suffer from a fundamental limitation: they forget everything between conversations. Every interaction starts from scratch, with no memory of user preferences, past discussions, or accumulated context. This creates a frustrating experience where users have to constantly re-explain themselves.

In this post, we'll build a Next.js chat application that uses [Hindsight](https://hindsight.vectorize.io) to give our AI assistant persistent memory across sessions. Each user gets their own isolated memory bank that remembers conversations, preferences, and personal details.

## What We're Building

Our chat application will have these key features:

- **🧠 Persistent Memory**: Each user gets their own memory bank that remembers conversations
- **🚀 Fast AI Responses**: Powered by OpenAI's GPT-4o
- **🎯 Per-User Context**: Isolated memory per user with automatic context retrieval
- **💬 Real-time Chat**: Instant responses with memory-augmented context

## The Architecture

Here's how our system works:

```
User Message
     ↓
Next.js API Route (/api/chat)
     ↓
1. Create/ensure user memory bank exists
     ↓
2. Hindsight.recall() → Get relevant memories
     ↓
3. OpenAI API → Generate response with memory context
     ↓
4. Hindsight.retain() → Store conversation
     ↓
Response to User
```

## Prerequisites

Before we start building, you'll need:

- Node.js 18+ installed
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [Hindsight API key](https://hindsight.vectorize.io) (sign up for Hindsight Cloud)

## Step 1: Setting Up Hindsight Cloud

Sign up at [hindsight.vectorize.io](https://hindsight.vectorize.io) and get your API key. No Docker or local server needed — Hindsight Cloud handles memory storage, fact extraction, and retrieval for you.

- **API endpoint**: `https://api.hindsight.vectorize.io`
- **Dashboard**: Log in at [hindsight.vectorize.io](https://hindsight.vectorize.io) to view stored memories

## Step 2: Create the Next.js Project

```bash
npx create-next-app@latest chat-memory --typescript --tailwind --app
cd chat-memory
```

Install our dependencies:

```bash
npm install @vectorize-io/hindsight-client openai marked uuid @tailwindcss/typography
npm install -D @types/uuid
```

## Step 3: Environment Configuration

Create `.env.local`:

```bash
OPENAI_API_KEY=your_openai_api_key_here
HINDSIGHT_API_URL=https://api.hindsight.vectorize.io
HINDSIGHT_API_KEY=your_hindsight_api_key_here
```

## Step 4: Building the Hindsight Integration

Create `lib/hindsight.ts` to handle all memory operations:

```typescript
import { HindsightClient } from '@vectorize-io/hindsight-client';

const hindsightClient = new HindsightClient({
  baseUrl: process.env.HINDSIGHT_API_URL || 'https://api.hindsight.vectorize.io',
  apiKey: process.env.HINDSIGHT_API_KEY,
});

export async function createUserBank(userId: string) {
  try {
    await hindsightClient.createBank(userId, {
      name: `Chat Memory for ${userId}`,
      background: "This is a conversational AI assistant that remembers user preferences, past conversations, and personal details shared during our interactions.",
      disposition: {
        empathy: 4,        // High empathy for better user experience
        skepticism: 2,     // Low skepticism to be trusting
        literalism: 3,     // Balanced interpretation
      }
    });
  } catch (error: any) {
    console.error('Error creating bank:', error);
    // Bank might already exist - don't throw
  }
}

export async function storeConversation(
  userId: string,
  userMessage: string,
  assistantMessage: string
) {
  try {
    const conversation = `User: ${userMessage}\nAssistant: ${assistantMessage}`;

    await hindsightClient.retain(userId, conversation, {
      context: 'conversation',
      metadata: { timestamp: new Date().toISOString() }
    });
  } catch (error) {
    console.error('Error storing conversation:', error);
    // Don't throw - let conversation continue even if storage fails
  }
}

export async function getRelevantMemories(userId: string, query: string) {
  try {
    const response = await hindsightClient.recall(userId, query, {
      maxTokens: 4096,
      budget: 'mid'
    });

    if (!response || !response.results) {
      console.warn('Hindsight API returned empty response');
      return '';
    }

    return response.results.map(memory => memory.text).join('\n');
  } catch (error) {
    console.error('Error retrieving memories:', error);
    return '';
  }
}
```

### Key Design Decisions

**Memory Bank Configuration**: Each user gets their own bank with high empathy (4) and low skepticism (2) to create a friendly, trusting assistant that remembers personal details.

**Error Handling**: We gracefully handle failures so the chat continues working even if Hindsight is unavailable.

**Async Storage**: We store conversations asynchronously after responding to avoid blocking the user experience.

## Step 5: OpenAI Integration for AI Responses

Create `lib/openai.ts`:

```typescript
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY!,
});

export async function generateChatResponse(
  userMessage: string,
  memories: string = '',
  userId: string
): Promise<string> {
  if (!process.env.OPENAI_API_KEY) {
    throw new Error('OPENAI_API_KEY environment variable is not set');
  }

  const systemPrompt = `You are a helpful AI assistant with memory. You remember past conversations and user preferences.

${memories ? `Here's what you remember about this user:\n${memories}\n` : 'No previous memories found for this user yet.'}

Be conversational, helpful, and reference relevant memories when appropriate. If this is the first conversation, introduce yourself and ask the user about themselves to start building memories.`;

  const completion = await openai.chat.completions.create({
    messages: [
      {
        role: 'system',
        content: systemPrompt,
      },
      {
        role: 'user',
        content: userMessage,
      },
    ],
    model: 'gpt-4o',
    temperature: 0.8,
    max_tokens: 4096,
  });

  return completion.choices[0]?.message?.content || 'I apologize, but I was unable to generate a response.';
}
```

## Step 6: The Chat API Route

Create `app/api/chat/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { generateChatResponse } from '@/lib/openai';
import { createUserBank, storeConversation, getRelevantMemories } from '@/lib/hindsight';

export async function POST(request: NextRequest) {
  try {
    const startTime = Date.now();
    const { message, userId } = await request.json();

    if (!message || !userId) {
      return NextResponse.json(
        { error: 'Message and userId are required' },
        { status: 400 }
      );
    }

    console.log('🚀 Starting chat request for user:', userId);

    // 1. Ensure user has a memory bank
    const bankStart = Date.now();
    await createUserBank(userId);
    console.log('🏦 Bank creation took:', Date.now() - bankStart, 'ms');

    // 2. Get relevant memories for context
    const memoryStart = Date.now();
    const memories = await getRelevantMemories(userId, message);
    console.log('🧠 Memory retrieval took:', Date.now() - memoryStart, 'ms');

    // 3. Generate response using OpenAI with memory context
    const llmStart = Date.now();
    const response = await generateChatResponse(message, memories, userId);
    console.log('🤖 LLM response took:', Date.now() - llmStart, 'ms');

    // 4. Store the conversation in Hindsight (async - don't wait)
    storeConversation(userId, message, response).catch(error => {
      console.error('Error storing conversation:', error);
    });

    console.log('⚡ Total request took:', Date.now() - startTime, 'ms');
    return NextResponse.json({ response });
  } catch (error) {
    console.error('Chat API error:', error);
    return NextResponse.json(
      { error: 'Failed to generate response' },
      { status: 500 }
    );
  }
}
```

### The Critical Flow

1. **Memory Bank Creation**: Ensures each user has their own isolated memory space
2. **Memory Retrieval**: Searches for relevant past conversations and details
3. **Context-Aware Generation**: OpenAI generates responses knowing what the user has shared before
4. **Memory Storage**: The new conversation gets stored for future context

## Step 7: Building the Chat Interface

Create `app/components/Chat.tsx`:

```typescript
'use client';

import { useState, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { marked } from 'marked';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [userId, setUserId] = useState<string>('');
  const [userName, setUserName] = useState<string>('');
  const [showUserSetup, setShowUserSetup] = useState(false);

  useEffect(() => {
    // Check if user has a stored identity
    const storedUserName = localStorage.getItem('chat-user-name');
    const storedUserId = localStorage.getItem('chat-user-id');

    if (storedUserName && storedUserId) {
      setUserName(storedUserName);
      setUserId(storedUserId);
    } else {
      setShowUserSetup(true);
    }
  }, []);

  const handleUserSetup = (name: string) => {
    const cleanName = name.trim().toLowerCase().replace(/[^a-z0-9]/g, '');
    const newUserId = `user-${cleanName}-${Date.now()}`;

    setUserName(name);
    setUserId(newUserId);
    setShowUserSetup(false);

    localStorage.setItem('chat-user-name', name);
    localStorage.setItem('chat-user-id', newUserId);
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading || !userId) return;

    const userMessage: Message = {
      id: uuidv4(),
      text: inputValue,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: inputValue,
          userId: userId,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to get response');
      }

      const assistantMessage: Message = {
        id: uuidv4(),
        text: data.response,
        isUser: false,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        id: uuidv4(),
        text: 'Sorry, I encountered an error. Please try again.',
        isUser: false,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // User setup component for first-time users
  const UserSetup = () => {
    const [tempName, setTempName] = useState('');

    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-100 dark:bg-gray-900 p-8">
        <div className="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg max-w-md w-full">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 text-center">
            Welcome to Chat with Memory
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6 text-center">
            Enter your name to start chatting. Your conversations will be remembered across sessions.
          </p>
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Enter your name (e.g., Alice, Bob, John)"
              value={tempName}
              onChange={(e) => setTempName(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && tempName.trim()) {
                  handleUserSetup(tempName);
                }
              }}
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              autoFocus
            />
            <button
              onClick={() => tempName.trim() && handleUserSetup(tempName)}
              disabled={!tempName.trim()}
              className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white py-2 px-4 rounded-lg transition-colors"
            >
              Start Chatting
            </button>
          </div>
        </div>
      </div>
    );
  };

  if (showUserSetup) {
    return <UserSetup />;
  }

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto bg-white dark:bg-gray-900">
      {/* Header */}
      <div className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-4">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
          Chat with Memory
        </h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Powered by OpenAI + Hindsight • Welcome back, {userName}!
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 dark:text-gray-400 mt-8">
            <p className="text-lg mb-2">👋 Hello {userName}! I'm your AI assistant with memory.</p>
            <p className="text-sm">I remember our past conversations. Ask me what I know about you, or tell me something new!</p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                message.isUser
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
              }`}
            >
              {message.isUser ? (
                <p className="whitespace-pre-wrap">{message.text}</p>
              ) : (
                <div
                  className="prose prose-sm max-w-none dark:prose-invert prose-gray"
                  dangerouslySetInnerHTML={{
                    __html: marked(message.text, { breaks: true, gfm: true })
                  }}
                />
              )}
              <p className={`text-xs mt-1 ${
                message.isUser ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'
              }`}>
                {message.timestamp.toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 dark:bg-gray-700 px-4 py-2 rounded-lg">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-4">
        <div className="flex space-x-2">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Type your message... (Press Enter to send)"
            className="flex-1 resize-none border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={1}
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!inputValue.trim() || isLoading || !userId}
            className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
```

## Step 8: Wire It All Together

Update `app/page.tsx`:

```typescript
import Chat from './components/Chat';

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
      <Chat />
    </div>
  );
}
```

Update `tailwind.config.js` to include prose styles:

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
```

## Step 9: Testing Your Memory-Enabled Chat

Start the development server:

```bash
npm run dev
```

Visit http://localhost:3000 and try these conversations:

**First session:**
```
You: Hi! I'm a software engineer from San Francisco. I love Python and machine learning.
AI: Hello! Nice to meet you! It's great to know you're a software engineer from San Francisco with a passion for Python and machine learning...
```

**Later session (refresh the page):**
```
You: What do you know about me?
AI: From our previous conversations, I remember that you're a software engineer based in San Francisco, and you have a strong interest in Python and machine learning...
```

Log in to the [Hindsight dashboard](https://hindsight.vectorize.io) to see your stored memories!

## Understanding the Memory Flow

Let's trace through what happens when a user sends a message:

1. **User Identity**: Each browser gets a unique user ID stored in localStorage
2. **Memory Bank Lookup**: The API checks if the user has a memory bank (creates if needed)
3. **Memory Retrieval**: Hindsight searches for relevant memories using semantic similarity
4. **Context Injection**: Memories are injected into the system prompt
5. **AI Response**: OpenAI generates a response with full knowledge of past conversations
6. **Memory Storage**: The conversation is stored for future reference

## Key Patterns for Memory-Enabled AI

### 1. Per-User Memory Banks
Each user gets their own isolated memory space, preventing data leakage:

```typescript
// Good: Isolated per user
await hindsightClient.recall(userId, query);

// Bad: Shared memory
await hindsightClient.recall('shared', query);
```

### 2. Graceful Degradation
The chat continues working even if memory is unavailable:

```typescript
export async function getRelevantMemories(userId: string, query: string) {
  try {
    const response = await hindsightClient.recall(userId, query);
    return response.results.map(memory => memory.text).join('\n');
  } catch (error) {
    console.error('Error retrieving memories:', error);
    return ''; // Return empty string, don't crash
  }
}
```

### 3. Async Memory Storage
Store memories asynchronously to avoid blocking the user:

```typescript
// Generate response first
const response = await generateChatResponse(message, memories, userId);

// Then store asynchronously (fire-and-forget)
storeConversation(userId, message, response).catch(error => {
  console.error('Error storing conversation:', error);
});

return NextResponse.json({ response });
```

### 4. Rich Context Injection
Provide clear context to the AI about what it remembers:

```typescript
const systemPrompt = `You are a helpful AI assistant with memory.

${memories ? `Here's what you remember about this user:\n${memories}\n` : 'No previous memories found for this user yet.'}

Be conversational and reference relevant memories when appropriate.`;
```

## Performance Considerations

### Memory Retrieval Speed
- **Budget levels**: Use 'low' for simple queries, 'mid' for balanced performance, 'high' for complex reasoning
- **Token limits**: Set `maxTokens` to control how much context to retrieve
- **Semantic search**: Hindsight's multi-strategy retrieval (semantic + keyword + graph + temporal) is optimized for sub-second responses

### Memory Storage Efficiency
- **Async storage**: Don't block user responses waiting for memory storage
- **Context categorization**: Use meaningful context labels like 'conversation', 'preferences', 'goals'
- **Batch operations**: For bulk imports, use Hindsight's batch retain API

## Advanced Features to Explore

### 1. Memory Types
Hindsight supports different memory types:
- **World**: Facts about the user ("Alice lives in SF")
- **Experience**: Conversations and events ("I helped with Python debugging")
- **Opinion**: AI-formed beliefs ("User prefers VS Code")

### 2. Temporal Queries
Enable time-based memory retrieval:
```typescript
const memories = await hindsightClient.recall(userId, "What did we discuss last week?", {
  maxTokens: 2048,
  budget: 'mid'
});
```

### 3. Memory Bank Disposition
Configure how your AI interprets information:
```typescript
await hindsightClient.createBank(userId, {
  disposition: {
    empathy: 5,      // Very empathetic
    skepticism: 1,   // Very trusting
    literalism: 2,   // Flexible interpretation
  }
});
```

## Deployment Considerations

### Production Setup
For production, you'll want:
- A managed PostgreSQL database with pgvector
- Hindsight deployed via Kubernetes or Docker Compose
- Proper API key management
- Memory bank cleanup policies

### Scaling
- Each user's memory bank is isolated, enabling horizontal scaling
- Hindsight's PostgreSQL backend scales with your database
- Consider memory retention policies for GDPR compliance

## Conclusion

We've built a chat application that remembers! By integrating Hindsight with Next.js and OpenAI, we created an AI assistant that:

- **Remembers** user preferences and past conversations
- **Provides context** from previous sessions
- **Scales** with per-user memory isolation
- **Performs well** with semantic memory retrieval

This pattern works for any application where continuity matters:
- Customer support bots that remember past issues
- Personal assistants that learn your preferences
- Educational apps that track learning progress
- Productivity tools that understand your workflow

The combination of Hindsight's sophisticated memory system with modern web frameworks opens up possibilities for truly intelligent, personalized AI applications.

Try building your own memory-enabled chat bot and experience the difference persistent memory makes!

## Resources

- [Hindsight Documentation](https://docs.hindsight.vectorize.io)
- [Example Repository](https://github.com/vectorize-io/hindsight-cookbook)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Next.js Documentation](https://nextjs.org/docs)