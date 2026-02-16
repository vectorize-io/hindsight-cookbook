# Go Concurrent Pipeline

Build a concurrent memory ingestion pipeline in Go. This recipe demonstrates how to use Go's concurrency primitives with the Hindsight client to ingest large datasets efficiently, then query them with recall and reflect.

## The Problem

You have a large dataset (log files, chat transcripts, documents) that needs to be ingested into Hindsight. Sequential ingestion is slow. Go's goroutines make it straightforward to parallelize.

## Architecture

```
                    ┌──────────┐
                    │  Source   │
                    │  (files,  │
                    │  API, DB) │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ Producer │  reads data, sends to channel
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼───┐ ┌───▼────┐ ┌──▼─────┐
         │Worker 1│ │Worker 2│ │Worker N│  concurrent RetainBatch
         └────┬───┘ └───┬────┘ └──┬─────┘
              │         │         │
              └─────────┼─────────┘
                        │
                  ┌─────▼─────┐
                  │ Hindsight │
                  │   API     │
                  └───────────┘
```

## Prerequisites

Hindsight server running (see [Go Quickstart](go-quickstart.md) for setup).

## The Pipeline

```go
package main

import (
    "bufio"
    "context"
    "fmt"
    "log"
    "os"
    "sync"
    "sync/atomic"
    "time"

    hindsight "github.com/vectorize-io/hindsight-client-go"
)

const (
    batchSize  = 10 // memories per batch
    numWorkers = 4  // concurrent workers
)

func main() {
    client, err := hindsight.New("http://localhost:8888")
    if err != nil {
        log.Fatal(err)
    }

    ctx := context.Background()
    bankID := "pipeline-demo"

    // Create the bank
    client.CreateBank(ctx, bankID,
        hindsight.WithBankName("Pipeline Demo"),
        hindsight.WithMission("Knowledge base ingested from documents"),
    )

    // Ingest from a file (one line = one memory)
    if len(os.Args) < 2 {
        fmt.Println("usage: pipeline <file>")
        os.Exit(1)
    }

    start := time.Now()
    count := ingest(ctx, client, bankID, os.Args[1])
    elapsed := time.Since(start)

    fmt.Printf("\nIngested %d memories in %s (%.1f/sec)\n",
        count, elapsed, float64(count)/elapsed.Seconds())

    // Query the ingested data
    fmt.Println("\n--- Recall ---")
    resp, _ := client.Recall(ctx, bankID, "What are the key topics?",
        hindsight.WithBudget(hindsight.BudgetHigh),
    )
    for _, r := range resp.Results {
        fmt.Printf("  - %s\n", r.Text)
    }

    fmt.Println("\n--- Reflect ---")
    answer, _ := client.Reflect(ctx, bankID, "Summarize everything you know")
    fmt.Println(answer.Text)
}

func ingest(ctx context.Context, client *hindsight.Client, bankID, filename string) int64 {
    f, err := os.Open(filename)
    if err != nil {
        log.Fatal(err)
    }
    defer f.Close()

    // Channel for batches
    batches := make(chan []hindsight.MemoryItem, numWorkers*2)
    var ingested atomic.Int64

    // Start workers
    var wg sync.WaitGroup
    for i := range numWorkers {
        wg.Add(1)
        go func(id int) {
            defer wg.Done()
            for batch := range batches {
                _, err := client.RetainBatch(ctx, bankID, batch)
                if err != nil {
                    log.Printf("worker %d: batch failed: %v", id, err)
                    continue
                }
                n := ingested.Add(int64(len(batch)))
                if n%100 == 0 {
                    fmt.Printf("  ingested %d memories...\n", n)
                }
            }
        }(i)
    }

    // Producer: read lines and batch them
    scanner := bufio.NewScanner(f)
    var batch []hindsight.MemoryItem

    for scanner.Scan() {
        line := scanner.Text()
        if line == "" {
            continue
        }
        batch = append(batch, hindsight.MemoryItem{Content: line})

        if len(batch) >= batchSize {
            batches <- batch
            batch = nil
        }
    }

    // Flush remaining
    if len(batch) > 0 {
        batches <- batch
    }

    close(batches)
    wg.Wait()

    return ingested.Load()
}
```

## Running It

Create a sample data file:

```bash
cat > sample_data.txt << 'EOF'
The Go programming language was created at Google in 2007
Go's concurrency model is based on CSP (Communicating Sequential Processes)
Goroutines are lightweight threads managed by the Go runtime
Channels provide typed conduits for communication between goroutines
The sync package provides mutexes, wait groups, and other synchronization primitives
Go modules were introduced in Go 1.11 for dependency management
The context package provides cancellation and deadline propagation
Go compiles to a single static binary with no external dependencies
The standard library includes an HTTP server, JSON parser, and crypto packages
Go 1.18 introduced generics with type parameters
EOF
```

```bash
go run . sample_data.txt
```

## Adding Tags for Partitioning

For larger datasets, use tags to partition memories by source or topic:

```go
func ingestWithTags(ctx context.Context, client *hindsight.Client, bankID, source string, lines []string) {
    var items []hindsight.MemoryItem
    for _, line := range lines {
        items = append(items, hindsight.MemoryItem{
            Content: line,
            Tags:    []string{source},
        })
    }

    _, err := client.RetainBatch(ctx, bankID, items,
        hindsight.WithDocumentTags([]string{"bulk-import", source}),
    )
    if err != nil {
        log.Printf("ingest %s failed: %v", source, err)
    }
}

// Later, recall only from a specific source
resp, _ := client.Recall(ctx, bankID, "What are the key concepts?",
    hindsight.WithRecallTags([]string{"go-docs"}),
    hindsight.WithRecallTagsMatch(hindsight.TagsMatchAnyStrict),
)
```

## Async Ingestion

For very large datasets, use async mode to avoid waiting for fact extraction:

```go
// Async retain returns immediately; processing happens in background
_, err := client.RetainBatch(ctx, bankID, items,
    hindsight.WithAsync(true),
)

// Check operation status via the ogen client
ogen := client.OgenClient()
ops, _ := ogen.ListOperations(ctx, ogenapi.ListOperationsParams{
    BankID: bankID,
})
```

## Graceful Shutdown

Use `context.WithCancel` for clean cancellation:

```go
ctx, cancel := context.WithCancel(context.Background())
defer cancel()

// In a signal handler:
sigCh := make(chan os.Signal, 1)
signal.Notify(sigCh, os.Interrupt)
go func() {
    <-sigCh
    fmt.Println("\nShutting down gracefully...")
    cancel()
}()

// Workers will stop when ctx is cancelled
```

## Performance Tips

| Tip | Why |
|-----|-----|
| Use `RetainBatch` over individual `Retain` | Fewer HTTP round trips |
| Set `batchSize` to 10-50 | Balances throughput vs. memory |
| Use 4-8 workers | Matches typical API concurrency limits |
| Use `WithAsync(true)` for bulk imports | Returns immediately, processes in background |
| Tag your data | Enables scoped recall without reingesting |

## Next Steps

- [Go Quickstart](go-quickstart.md) - Basic retain, recall, reflect
- [Go SDK Docs](https://hindsight.vectorize.io/sdks/go) - Full API reference
