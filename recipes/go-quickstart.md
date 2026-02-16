# Go Quickstart

Get started with the Hindsight Go client in under 5 minutes. This recipe covers the three core operations: **retain**, **recall**, and **reflect**.

## Prerequisites

Make sure you have Hindsight running. The easiest way is via Docker:

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

## Installation

```bash
go get github.com/vectorize-io/hindsight-client-go
```

## Connect to Hindsight

```go
package main

import (
    "context"
    "fmt"
    "log"

    hindsight "github.com/vectorize-io/hindsight-client-go"
)

func main() {
    client, err := hindsight.New("http://localhost:8888")
    if err != nil {
        log.Fatal(err)
    }

    ctx := context.Background()
    bankID := "go-quickstart"
```

## Retain: Store Information

The `Retain` operation pushes new memories into Hindsight. Behind the scenes, an LLM extracts key facts, temporal data, entities, and relationships.

```go
    // Simple retain
    _, err = client.Retain(ctx, bankID,
        "Alice works at Google as a software engineer",
    )
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println("Stored memory about Alice's job")

    // Retain with context and timestamp
    _, err = client.Retain(ctx, bankID,
        "Alice got promoted to senior engineer",
        hindsight.WithContext("career update"),
        hindsight.WithTimestamp(time.Date(2025, 6, 15, 10, 0, 0, 0, time.UTC)),
    )
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println("Stored memory about Alice's promotion")
```

## Retain Batch: Store Multiple Memories

```go
    items := []hindsight.MemoryItem{
        {Content: "Bob is a data scientist who works with Alice"},
        {Content: "Charlie manages the team and reports to the VP of Engineering"},
        {Content: "The team is working on a recommendation engine using Go"},
    }

    resp, err := client.RetainBatch(ctx, bankID, items)
    if err != nil {
        log.Fatal(err)
    }
    fmt.Printf("Stored %d memories\n", resp.ItemsCount)
```

## Recall: Retrieve Memories

`Recall` retrieves memories matching a query using four parallel strategies: semantic similarity, keyword matching, entity/relationship graph traversal, and temporal filtering.

```go
    // Simple recall
    results, err := client.Recall(ctx, bankID, "What does Alice do?")
    if err != nil {
        log.Fatal(err)
    }

    fmt.Println("\nMemories about Alice:")
    for _, r := range results.Results {
        fmt.Printf("  - %s\n", r.Text)
    }
```

```go
    // Recall with options
    results, err = client.Recall(ctx, bankID, "Who works on the team?",
        hindsight.WithBudget(hindsight.BudgetHigh),
        hindsight.WithMaxTokens(2048),
        hindsight.WithTypes([]string{"world"}),
    )
    if err != nil {
        log.Fatal(err)
    }

    fmt.Println("\nTeam memories (world facts only):")
    for _, r := range results.Results {
        fmt.Printf("  - [%s] %s\n", r.Type.Or("?"), r.Text)
    }
```

## Reflect: Generate Insights

`Reflect` performs disposition-aware reasoning over stored memories. It retrieves relevant context, then uses an LLM to synthesize a response. Great for summarization, analysis, and Q&A.

```go
    answer, err := client.Reflect(ctx, bankID,
        "What should I know about this team?",
    )
    if err != nil {
        log.Fatal(err)
    }

    fmt.Println("\nReflection:")
    fmt.Println(answer.Text)
```

## Full Program

Here's the complete program:

```go
package main

import (
    "context"
    "fmt"
    "log"
    "time"

    hindsight "github.com/vectorize-io/hindsight-client-go"
)

func main() {
    client, err := hindsight.New("http://localhost:8888")
    if err != nil {
        log.Fatal(err)
    }

    ctx := context.Background()
    bankID := "go-quickstart"

    // 1. Store memories
    client.Retain(ctx, bankID, "Alice works at Google as a software engineer")
    client.Retain(ctx, bankID, "Alice got promoted to senior engineer",
        hindsight.WithContext("career update"),
        hindsight.WithTimestamp(time.Date(2025, 6, 15, 10, 0, 0, 0, time.UTC)),
    )

    items := []hindsight.MemoryItem{
        {Content: "Bob is a data scientist who works with Alice"},
        {Content: "Charlie manages the team and reports to the VP of Engineering"},
        {Content: "The team is working on a recommendation engine using Go"},
    }
    client.RetainBatch(ctx, bankID, items)

    // 2. Recall memories
    results, _ := client.Recall(ctx, bankID, "What does Alice do?")
    fmt.Println("Memories about Alice:")
    for _, r := range results.Results {
        fmt.Printf("  - %s\n", r.Text)
    }

    // 3. Reflect
    answer, _ := client.Reflect(ctx, bankID, "What should I know about this team?")
    fmt.Printf("\nReflection:\n%s\n", answer.Text)

    // 4. Cleanup
    client.DeleteBank(ctx, bankID)
}
```

## Memory Types

Hindsight organizes memory into distinct networks:

| Type | Description | Example |
|------|-------------|---------|
| **World** | Facts about the world | "Alice works at Google" |
| **Experience** | Agent's own experiences | "I helped Alice debug her code" |
| **Observation** | Complex models from reflection | "Alice is a senior IC focused on ML" |

## Next Steps

- [Go Concurrent Pipeline](go-concurrent-pipeline.md) - Build a concurrent ingestion pipeline
- [Go SDK Docs](https://hindsight.vectorize.io/sdks/go) - Full API reference
