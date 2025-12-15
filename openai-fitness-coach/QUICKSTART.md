# Quick Start - OpenAI + Hindsight Integration

Get up and running in 3 minutes!

## Prerequisites

1. **OpenAI API Key**
   ```bash
   export OPENAI_API_KEY=your_openai_api_key
   ```

2. **Hindsight API Running**
   ```bash
   # Follow Hindsight setup instructions
   # API should be running at http://localhost:8888
   ```

3. **Install Dependencies**
   ```bash
   pip install openai requests
   ```

## Run the Demo

```bash
cd openai-fitness-coach
python demo_conversational.py
```

**What the demo does:**
1. Sets a fitness goal
2. Logs sample workouts and meals
3. Chats with OpenAI Agent (which retrieves memories from Hindsight)
4. Shows how function calling bridges OpenAI + Hindsight

## Chat with Your Coach

After the demo, try chatting:

```bash
python openai_coach.py
```

**Example questions:**
- "What did I do for training this week?"
- "Based on my workouts, should I rest today?"
- "How is my nutrition supporting my goals?"
- "What's my progress toward my goal?"

## What's Happening Behind the Scenes

When you ask: *"What did I do this week?"*

1. **OpenAI Assistant** receives your question
2. **Decides to call function:** `search_workouts(after_date="2024-11-18")`
3. **Function calls Hindsight API** to retrieve workout memories
4. **Hindsight returns** relevant workouts with temporal context
5. **OpenAI generates response** using retrieved memories
6. **You get personalized answer** based on your actual data!

## Architecture

```
You: "What did I run this week?"
    |
OpenAI Assistant
    |
Function Call: search_workouts()
    |
Hindsight API (retrieves memories)
    |
OpenAI Assistant (generates response)
    |
"You ran 45 minutes on Monday and 60 minutes on Wednesday!"
```

## Comparison to Standard Demo

| Feature | OpenAI + Hindsight | Standard Hindsight |
|---------|-----------------|-----------------|
| Conversation | OpenAI Assistant | Hindsight `/think` |
| Memory | Hindsight (via functions) | Hindsight (built-in) |
| LLM Provider | OpenAI only | Configurable |
| Integration | Function calling | Direct API |
| Best For | OpenAI users | Hindsight-native apps |

## Key Insight

This example shows how to **add sophisticated memory to any OpenAI Agent**:
- OpenAI handles conversation
- Hindsight handles memory (storage, retrieval, temporal queries)
- Function calling bridges them

**You can apply this pattern to:**
- Customer support bots
- Personal assistants
- Educational tutors
- Any agent that needs to remember!

## Next Steps

1. Run `python demo_conversational.py` to see it work
2. Chat with `python openai_coach.py`
3. Log your own workouts/meals
4. Read `README.md` for deeper understanding
5. Customize for your own use case!

## Troubleshooting

**"OPENAI_API_KEY not set"**
```bash
export OPENAI_API_KEY=your_key_here
```

**"Connection refused"**
- Make sure Hindsight API is running

**"Agent not found"**
- Create the fitness-coach agent in Hindsight

---

**Ready? Let's go!**
```bash
python demo_conversational.py
```
