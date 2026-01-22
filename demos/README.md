# Hindsight Demo Applications

Example applications showcasing Hindsight's memory capabilities across different use cases.

## Setup

### Option 1: Using Local Hindsight (Recommended for Testing)

1. **Start Hindsight via Docker:**

```bash
export OPENAI_API_KEY="your-openai-api-key"

docker run --rm -it --pull always -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  -e HINDSIGHT_API_LLM_MODEL=o3-mini \
  -v $HOME/.hindsight-docker:/home/hindsight/.pg0 \
  ghcr.io/vectorize-io/hindsight:latest
```

- API: http://localhost:8888
- UI: http://localhost:9999

2. **Install Dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure Environment:**

```bash
export HINDSIGHT_BASE_URL="http://localhost:8888"
export OPENAI_API_KEY="your-openai-api-key"

# Optional: for real web search in personalized_search.py
# Get a key at https://tavily.com/
export TAVILY_API_KEY="your-tavily-api-key"
```

4. **Run a demo:**

```bash
python movie_recommendation.py
```

### Option 2: Using Hindsight Cloud

1. **Get a Hindsight API Key:**

   Sign up at [https://ui.hindsight.vectorize.io/](https://ui.hindsight.vectorize.io/) to get your API key.

2. **Install Dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure Environment:**

```bash
export HINDSIGHT_API_KEY="your-hindsight-api-key"
export OPENAI_API_KEY="your-openai-api-key"

# Optional: for real web search in personalized_search.py
# Get a key at https://tavily.com/
export TAVILY_API_KEY="your-tavily-api-key"
```

Note: The demos default to the Hindsight Cloud API at `https://api.hindsight.vectorize.io`. You can override this by setting `HINDSIGHT_BASE_URL`.

3. **Run a demo:**

```bash
python movie_recommendation.py
```

## Demo Applications

### 1. Movie Recommendation (`movie_recommendation.py`)

A personalized movie recommender that learns your tastes over time.

**Features:**
- Remembers favorite genres, directors, and actors
- Tracks movies you've watched and enjoyed
- Provides contextual recommendations based on mood

```bash
python movie_recommendation.py
```

### 2. Fitness Tracker (`fitness_tracker.py`)

A fitness coach that tracks workouts, diet, and recovery.

**Features:**
- Logs workout sessions with exercises and weights
- Tracks meals and dietary preferences
- Monitors recovery and sleep patterns
- Provides personalized training advice

```bash
python fitness_tracker.py
```

### 3. Study Buddy (`study_buddy.py`)

A personalized study assistant for students.

**Features:**
- Tracks study sessions and topics covered
- Monitors confidence levels per topic
- Identifies knowledge gaps
- Suggests topics for spaced repetition review

```bash
python study_buddy.py
```

### 4. Personalized Search (`personalized_search.py`)

A search agent that learns your preferences for better results.

**Features:**
- Learns location, dietary restrictions, and lifestyle
- Personalizes search queries based on context
- Remembers past searches and preferences
- Integrates with Tavily for real web search (optional)

**Optional: Real Web Search**

By default, this demo uses simulated search results. For real web search, get a Tavily API key at [https://tavily.com/](https://tavily.com/):

```bash
export TAVILY_API_KEY="your-tavily-api-key"
python personalized_search.py
```

### 5. Healthcare Assistant (`healthcare_assistant.py`)

A supportive healthcare chatbot (demo purposes only).

**Features:**
- Tracks symptoms, medications, and allergies
- Maintains patient history across conversations
- Provides health information and wellness tips
- Schedules appointments

**Disclaimer:** This is a demo application. Not for real medical advice.

```bash
python healthcare_assistant.py
```

### 6. Personal Assistant (`personal_assistant.py`)

A general-purpose assistant with long-term memory.

**Features:**
- Remembers family, work, and personal details
- Tracks preferences and habits
- Helps with scheduling and reminders
- Maintains context across conversations

```bash
python personal_assistant.py
```

## Key Concepts Demonstrated

### Memory Operations

Each demo showcases the three core Hindsight operations:

| Operation | Purpose | Example |
|-----------|---------|---------|
| `retain()` | Store memories | Log a workout, save a preference |
| `recall()` | Retrieve relevant memories | Find past preferences for context |
| `reflect()` | Synthesize insights | Generate progress reports, summaries |

### Memory Banks

Each demo uses a unique `bank_id` to isolate memories:

```python
# Each user/patient/student gets their own memory bank
bank_id = f"patient-{patient_id}"
bank_id = f"student-{student_id}"
```

### Contextual Retrieval

Demos show how to retrieve relevant context before generating responses:

```python
# Get relevant memories
memories = hindsight.recall(bank_id, query, budget="high")

# Build context string
context = "\n".join(m.text for m in memories.results)

# Use in LLM prompt
prompt = f"User context:\n{context}\n\nUser question: {question}"
```

### Temporal Patterns

Several demos include timestamps for temporal queries:

```python
today = datetime.now().strftime("%B %d, %Y")
content = f"{today} - WORKOUT: Bench press 3x8 @ 60kg"
```

### Client Cleanup

Always close the Hindsight client when done to properly clean up connections:

```python
# At the end of your application
hindsight.close()
```

Or use the context manager pattern:

```python
with Hindsight(api_key=api_key, base_url=base_url) as hindsight:
    hindsight.retain(bank_id="user", content="Hello")
    # ... client automatically closed when exiting the block
```

## Adapting for Your Use Case

1. **Choose your memory structure** - Decide what categories of information to track
2. **Design your bank_id scheme** - One bank per user, or per user+context
3. **Balance recall vs reflect** - Use `recall` for retrieval, `reflect` for synthesis
4. **Add timestamps** - Include dates in content for temporal queries
5. **Iterate on prompts** - Tune how you incorporate memories into LLM prompts

## Resources

- [Hindsight Documentation](https://hindsight.vectorize.io)
- [API Reference](https://hindsight.vectorize.io/developer/api)
- [GitHub Repository](https://github.com/vectorize-io/hindsight)
