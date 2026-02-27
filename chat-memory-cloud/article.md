# How the Chat Memory Demo Works

This article explains the technical details of how the Chat Memory app integrates Hindsight Cloud to give an LLM persistent, per-user memory. Every message the user sends triggers a recall-before-response, retain-after-response cycle that builds a growing knowledge base the assistant can draw from across sessions.

---

## The Request Lifecycle

Every chat message goes through five steps, all inside a single API route handler (`app/api/chat/route.ts`):

```
1. Ensure memory bank exists  →  createBank (PUT, idempotent)
2. Recall relevant memories    →  recall(userId, message)
3. Inject memories into prompt →  system prompt construction
4. Generate LLM response       →  OpenAI or Groq completion
5. Retain the conversation     →  retain(userId, conversation)  [fire-and-forget]
```

Steps 1-4 are sequential — each depends on the previous result. Step 5 runs asynchronously after the response is already sent to the user, so memory storage never adds latency to the chat experience.

Here's what each step does in detail.

---

## Step 1: Ensure the Memory Bank Exists

```typescript
await hindsightClient.createBank(userId, {
  name: `Chat Memory for ${userId}`,
  background: "This is a conversational AI assistant that remembers user preferences, past conversations, and personal details shared during our interactions.",
  disposition: {
    empathy: 4,
    skepticism: 2,
    literalism: 3,
  }
});
```

Every user gets their own isolated memory bank in Hindsight, identified by their `userId`. The `createBank` call is a PUT — it's idempotent. If the bank already exists, this is a no-op. If the user is new, it creates a fresh bank.

Three things are configured on the bank:

**Background** — A natural language description of what this memory bank is for. Hindsight uses this to guide fact extraction. When it processes a conversation, it knows to focus on "user preferences, past conversations, and personal details" rather than ephemeral details like timestamps or UI interactions.

**Disposition** — Three personality traits that influence how Hindsight interprets and consolidates information:

- `empathy: 4` (high) — The system reads between the lines. If a user says "I've been struggling with React," it captures not just the fact but the emotional context.
- `skepticism: 2` (low) — The system trusts what the user says at face value rather than questioning claims.
- `literalism: 3` (balanced) — Middle ground between literal interpretation and inferring implicit meaning.

These traits don't affect how information is stored — they influence how Hindsight reasons about accumulated knowledge during reflect operations and observation consolidation.

---

## Step 2: Recall Relevant Memories

```typescript
const memories = await getRelevantMemories(userId, message);
```

Which calls:

```typescript
const response = await hindsightClient.recall(userId, query, {
  maxTokens: 4096,
  budget: 'mid'
});

return response.results.map(memory => memory.text).join('\n');
```

This is where the magic happens. Before the LLM generates a response, the user's message is sent to Hindsight as a recall query. Hindsight runs four parallel search strategies against the user's memory bank:

1. **Semantic search** — Finds memories that are conceptually related to the query, even if different words are used. "What's my favorite language?" matches a memory about "User loves Python."
2. **Keyword search (BM25)** — Exact term matching. Ensures specific names, tools, and technologies mentioned in the query are found.
3. **Graph traversal** — Follows entity connections in the knowledge graph. If the user asks about "my projects," graph traversal can follow connections from the user to technologies to specific projects mentioned in past conversations.
4. **Temporal search** — Understands time references and prioritizes recent information.

Results from all four strategies are fused using Reciprocal Rank Fusion (RRF) — memories that appear in multiple strategies rank higher. A cross-encoder neural model re-ranks the final results for relevance.

Two parameters control the quality/speed tradeoff:

- `budget: 'mid'` — Controls search depth. `'mid'` is a balanced setting that explores the knowledge graph reasonably without the latency of deep multi-hop traversal. For a chat app, this is the right tradeoff — fast enough for conversational latency, thorough enough to find relevant context.
- `maxTokens: 4096` — The token budget for returned memories. Hindsight fills this budget with the highest-ranked results, stopping when the budget is exhausted. This maps directly to how much context will be injected into the LLM prompt.

The result is a list of memory objects, each with a `.text` field containing a synthesized fact. These are joined into a single string for prompt injection.

### What gets recalled

Hindsight doesn't return raw conversation transcripts. During the retain process (step 5), it extracts structured facts from conversations. So a conversation like:

```
User: I'm a software engineer from San Francisco. I love Python and machine learning.
Assistant: Nice to meet you! That's a great combination...
```

Gets stored as facts like:
- "User is a software engineer"
- "User is from San Francisco"
- "User loves Python"
- "User is interested in machine learning"

When the user later asks "What do you know about me?", recall returns these distilled facts — not the original conversation text.

Over time, Hindsight also consolidates related facts into **observations** — higher-level synthesized knowledge:

> "User is a San Francisco-based software engineer with strong interests in Python and machine learning, who prefers VS Code as their editor."

Observations are included in recall results alongside raw facts, providing richer context to the LLM.

---

## Step 3: Inject Memories into the Prompt

```typescript
const systemPrompt = `You are a helpful AI assistant with memory. You remember past conversations and user preferences.

${memories
  ? `Here's what you remember about this user:\n${memories}\n`
  : 'No previous memories found for this user yet.'}

Be conversational, helpful, and reference relevant memories when appropriate.
If this is the first conversation or no memories are available, introduce yourself
and ask the user about themselves to start building memories.`;
```

The recalled memories are injected directly into the system prompt. The LLM sees them as context it "remembers" about the user. This is straightforward prompt engineering — there's no special memory-aware model needed. Any LLM works because the memories are just text in the system prompt.

The prompt also instructs the LLM to behave differently when no memories exist (first conversation) versus when it has context (returning user). This creates a natural experience where the assistant starts by getting to know you and progressively becomes more personalized.

For a first-time user, the system prompt contains:
```
No previous memories found for this user yet.
```

For a returning user, it might contain:
```
Here's what you remember about this user:
User is a software engineer based in San Francisco
User loves Python and machine learning
User prefers VS Code over other editors
User is working on a React project
User mentioned they're interested in TypeScript lately
```

---

## Step 4: Generate the LLM Response

```typescript
const completion = await client.chat.completions.create({
  messages: [
    { role: 'system', content: systemPrompt },
    { role: 'user', content: userMessage },
  ],
  model,
  temperature: 0.8,
  max_tokens: 4096,
});
```

The app supports two LLM providers, selectable via the `LLM_PROVIDER` environment variable:

- **OpenAI** (`gpt-4o`) — Default. High quality responses.
- **Groq** (`qwen/qwen3-32b`) — Alternative. Faster inference via Groq's hardware.

Both use the same chat completions API shape (Groq's SDK mirrors OpenAI's interface), so the provider swap is transparent. The only difference is that Groq models sometimes emit `<think>` tags for chain-of-thought reasoning, which are stripped from the response.

Note that only the current user message is sent to the LLM — not the full conversation history. This is intentional. The app doesn't maintain a message history on the server between requests. Instead, Hindsight serves as the memory layer. Each request is stateless from the LLM's perspective: system prompt (with recalled memories) + single user message. The memories provide continuity that would normally require sending the full chat history.

This has a tradeoff: within a single session, the LLM doesn't see earlier messages in the current conversation. It relies on Hindsight to recall relevant context from those messages after they've been retained. For a demo, this keeps the architecture simple. A production app might combine both approaches — short-term conversation history in the prompt plus long-term Hindsight memories in the system prompt.

---

## Step 5: Retain the Conversation

```typescript
// Fire-and-forget — don't block the response
storeConversation(userId, message, response).catch(error => {
  console.error('Error storing conversation:', error);
});
```

Which calls:

```typescript
const conversation = `User: ${userMessage}\nAssistant: ${assistantMessage}`;

await hindsightClient.retain(userId, conversation, {
  context: 'conversation',
  metadata: { timestamp: new Date().toISOString() }
});
```

After the response is sent to the user, the conversation turn (user message + assistant response) is retained to Hindsight. This is fire-and-forget — the `.catch()` handles errors silently so the user never waits for memory storage.

Three things happen inside Hindsight when `retain()` is called:

### Fact Extraction

Hindsight analyzes the conversation text and extracts structured facts. It produces two types:

- **World facts** — Objective information about the user. "User works at Google." "User prefers dark mode."
- **Experiences** — Events and interactions. "User asked about Python frameworks." "Assistant recommended FastAPI."

The bank's `background` guides what gets extracted. Since this bank is configured for "user preferences, past conversations, and personal details," the extraction focuses on those categories.

### Entity Recognition and Graph Construction

Entities (people, places, technologies, concepts) are identified and linked in a knowledge graph. If the user mentions "Python" in three different conversations, all three facts are connected through the "Python" entity node. This enables graph-based recall — asking about "my programming languages" can traverse from the user entity to all connected language entities.

### Observation Consolidation

After facts are stored, Hindsight runs a background consolidation process. Related facts are synthesized into observations — higher-level knowledge representations. If five separate conversations mention Python in different contexts, the consolidation engine might produce:

> "User is a Python enthusiast who uses it for machine learning, data analysis, and web development with FastAPI. They prefer Python over JavaScript for backend work."

This observation captures patterns that no single fact contains. Observations are automatically included in future recall results.

### The `context` Parameter

The `context: 'conversation'` parameter tells Hindsight's extraction engine the type of content being retained. This helps it interpret the text correctly — it knows this is a dialogue, not a document or a structured record.

---

## Per-User Isolation

Each user gets a completely separate memory bank. User A's memories are never mixed with User B's. This is enforced by using the `userId` as the bank ID in every Hindsight call:

```typescript
hindsightClient.createBank(userId, ...)   // bank per user
hindsightClient.recall(userId, ...)       // search only this user's bank
hindsightClient.retain(userId, ...)       // store only to this user's bank
```

The `userId` is generated on the client side when the user first enters their name:

```typescript
const newUserId = `user-${cleanName}-${Date.now()}`;
```

It's stored in `localStorage`, so the same browser session always uses the same identity. The user can "Switch User" to create a new identity with a fresh memory bank.

---

## What Hindsight Cloud Handles

The app delegates all memory complexity to Hindsight Cloud:

| Concern | Handled by |
|---------|-----------|
| Fact extraction from conversations | Hindsight |
| Entity recognition and resolution | Hindsight |
| Knowledge graph construction | Hindsight |
| Multi-strategy search (semantic, keyword, graph, temporal) | Hindsight |
| Result ranking and fusion | Hindsight |
| Observation consolidation | Hindsight |
| Per-user bank isolation | Hindsight |
| Token budget management | Hindsight |

The application code is ~100 lines across three files (`lib/hindsight.ts`, `lib/llm.ts`, `app/api/chat/route.ts`). Everything else — the React frontend, user identity management, message display — is standard web app code with no memory-specific logic.

---

## Timing

The API route logs timing for each step:

```
🚀 Starting chat request for user: user-alice-1234567890
🏦 Bank creation took: 45 ms        (idempotent PUT, fast when bank exists)
🧠 Memory retrieval took: 180 ms    (recall with mid budget)
🤖 LLM response took: 1200 ms       (GPT-4o completion)
⚡ Total request took: 1425 ms
```

Memory recall adds ~150-250ms to each request. The retain happens after the response is sent, so it adds zero latency to the user experience. The dominant cost is always the LLM completion.
