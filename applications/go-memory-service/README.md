# Go Memory-Augmented API

A Go HTTP microservice that combines a domain API with Hindsight memory. Each API user gets a personal memory bank. The service remembers past interactions and uses them to provide personalized responses.

## Use Case

A **developer knowledge assistant** that remembers what technologies each user works with, what problems they've solved, and provides personalized recommendations.

## Features

- Per-user memory banks (created on first interaction)
- Conversation history stored via retain
- Context-aware responses via recall + reflect
- Structured output for programmatic consumption
- Health check and bank stats endpoints

## Running

### 1. Start Hindsight

```bash
export OPENAI_API_KEY=your-key

docker run --rm -it --pull always -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  -e HINDSIGHT_API_LLM_MODEL=o3-mini \
  -v $HOME/.hindsight-docker:/home/hindsight/.pg0 \
  ghcr.io/vectorize-io/hindsight:latest
```

### 2. Start the service

```bash
go run main.go
```

### 3. Try it out

```bash
# Teach it something
curl -s localhost:8080/learn -d '{
  "user_id": "alice",
  "content": "I am building a Go microservice that uses gRPC and PostgreSQL",
  "tags": ["project"]
}' | jq .

# Teach it more
curl -s localhost:8080/learn -d '{
  "user_id": "alice",
  "content": "I solved a connection pooling issue by switching from pgx to pgxpool",
  "tags": ["debugging"]
}'

curl -s localhost:8080/learn -d '{
  "user_id": "alice",
  "content": "I prefer structured logging with slog over zerolog",
  "tags": ["preferences"]
}'

# Ask a question (uses recall + reflect)
curl -s localhost:8080/ask -d '{
  "user_id": "alice",
  "query": "What tech stack am I using?"
}' | jq .

# Raw recall
curl -s "localhost:8080/recall/alice?q=database" | jq .
```

## How It Works

1. **`/learn`** - Stores information using `Retain`. Each piece of info becomes searchable facts, entities, and relationships.

2. **`/ask`** - Two-phase retrieval:
   - **Recall**: Finds relevant facts from the user's memory bank
   - **Reflect**: Synthesizes a response using those facts plus disposition-aware reasoning
   - The Q&A interaction itself is stored as a new memory (fire-and-forget goroutine)

3. **`/recall/{userID}`** - Direct access to raw recalled facts for debugging or building custom UIs.

## Key Patterns

### Per-User Isolation

Each user gets their own bank (`user-alice`, `user-bob`). Banks are created lazily on first interaction via `CreateBank` (idempotent - safe to call repeatedly).

### Fire-and-Forget Memory

The `/ask` handler stores the interaction in a background goroutine so the response isn't delayed by the retain call:

```go
go func() {
    bgCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()
    client.Retain(bgCtx, bankID, interaction)
}()
```

### Tag-Based Scoping

Tags partition memories within a bank. Query only `debugging` memories, or only `preferences`:

```bash
# The /recall endpoint could be extended to support tag filtering:
curl "localhost:8080/recall/alice?q=issues&tags=debugging"
```

## Next Steps

- [Go Quickstart](../../recipes/go-quickstart.md) - Core operations walkthrough
- [Go Concurrent Pipeline](../../recipes/go-concurrent-pipeline.md) - Bulk data ingestion
- [Go SDK Docs](https://hindsight.vectorize.io/sdks/go) - Full API documentation
