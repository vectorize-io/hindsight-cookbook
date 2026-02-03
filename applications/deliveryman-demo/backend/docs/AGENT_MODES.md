# Agent Modes Documentation

This document explains each agent mode in the deliveryman benchmark and how they behave with different settings.

## Overview

| Mode | Memory Source | Mental Models | Bank Mission |
|------|---------------|---------------|--------------|
| `no_memory` | None | No | No |
| `filesystem` | In-memory notes (LLM-updated) | No | No |
| `recall` | Hindsight (raw facts) | No | No |
| `reflect` | Hindsight (LLM synthesis) | No | No |
| `hindsight_mm` | Hindsight + Mental Models | Yes (wait) | Yes |
| `hindsight_mm_nowait` | Hindsight + Mental Models | Yes (no wait) | Yes |

---

## Mode Details

### 1. NO_MEMORY

**Description:** Baseline mode with no memory system. The agent has no knowledge of past deliveries.

**System Prompt:** `"You are a delivery agent. Use the tools provided to get it delivered."`

**Behavior:** Agent explores the building from scratch each delivery. No information persists between deliveries.

**Example:**
```
Delivery 1: "Deliver to John Smith" → Agent explores, finds John on Floor 2 Front
Delivery 2: "Deliver to John Smith" → Agent explores again (no memory of Delivery 1)
```

---

### 2. FILESYSTEM (with inject_once)

**Description:** Agent-managed notes with automatic read at start and LLM-based write at end. Notes persist between deliveries but are not processed by Hindsight.

**Memory Query Mode:** `inject_once`

**System Prompt:** Simple delivery prompt (notes are auto-injected)

**Tools:** Normal navigation tools only (no read_notes/write_notes)

**Note Writing:** Uses an LLM to update notes based on delivery outcome. The LLM is prompted to:
- Keep notes concise and scannable
- Focus on useful information (employee locations, business names)
- Update or correct existing information
- Note patterns or tips discovered
- Learn from failures too (e.g., "John is NOT on Floor 1")

**Execution Flow:**
1. System auto-reads notes and injects into prompt under `# Your Notes`
2. Agent runs normal delivery
3. System calls LLM to update notes based on delivery outcome

**Example:**
```
Delivery 1:
  System reads notes → empty
  Agent explores, finds John on Floor 2 Front, delivers (SUCCESS)
  LLM updates notes → "John Smith - Floor 2 Front, TechCorp"

Delivery 2 (failed):
  System reads notes → "John Smith - Floor 2 Front, TechCorp"
  Agent tries to find Sarah, runs out of steps (FAILED)
  LLM updates notes → "John Smith - Floor 2 Front, TechCorp
                       Sarah Kim - searched Floor 1, not found there"

Delivery 3:
  System injects notes into prompt
  Agent uses notes to avoid Floor 1 for Sarah, finds her on Floor 3
  LLM updates notes → "John Smith - Floor 2 Front, TechCorp
                       Sarah Kim - Floor 3 Back, DataCorp"
```

---

### 2b. FILESYSTEM (with per_step)

**Description:** Agent has read_notes tool available to query notes at any time during delivery. Writing is LLM-controlled by the system at the end.

**Memory Query Mode:** `per_step`

**System Prompt:** Includes guidance on using read_notes tool

**Tools:** Normal navigation tools + `read_notes()` (no write_notes - system controls writing via LLM)

**Execution Flow:**
1. Agent receives instructions about read_notes tool
2. Agent can call read_notes() at any point during delivery
3. System calls LLM to update notes at end based on delivery outcome

**Example:**
```
Delivery 1:
  Agent calls read_notes() → "Your notes file is empty"
  Agent explores, finds John, delivers
  LLM updates notes: "John Smith - Floor 2 Front, TechCorp"

Delivery 2:
  Agent calls read_notes() mid-delivery → "John Smith - Floor 2 Front, TechCorp"
  Agent uses this info, then continues exploring for Sarah
  LLM updates notes with both John and Sarah's info
```

**Note:** Writing notes is always controlled by the system via LLM to ensure consistent, useful information is recorded. This makes filesystem mode comparable to Hindsight which also uses LLM processing.

---

### 2c. FILESYSTEM (with both)

**Description:** Combines inject_once and per_step. Notes are auto-injected at start AND agent has read_notes tool available.

**Memory Query Mode:** `both`

**Tools:** Normal navigation tools + `read_notes()`

**Execution Flow:**
1. System auto-reads notes and injects into prompt under `# Your Notes`
2. Agent can also call read_notes() at any point during delivery
3. System calls LLM to update notes at end

**Use case:** Agent gets initial context but can also re-check notes mid-delivery if needed.

---

### 3. RECALL (with inject_once)

**Description:** Queries Hindsight's recall API once at the start of delivery. Returns raw facts from the memory bank.

**Memory Query Mode:** `inject_once`

**Behavior:**
1. Before delivery starts, system queries: `"Where does {recipient} work?"`
2. Hindsight returns matching facts (e.g., `"John Smith works at TechCorp on floor 2"`)
3. Facts are injected into system prompt under `# Relevant Memory`
4. Agent uses this information for the entire delivery

**Example:**
```
System queries Hindsight: "Where does John Smith work?"
Hindsight returns: "- John Smith works at TechCorp on floor 2, front side"
System prompt includes: "# Relevant Memory\n- John Smith works at TechCorp..."
Agent reads memory and navigates directly to Floor 2 Front
```

**Why no per_step for RECALL?** Recall returns raw facts from the database. These facts (e.g., "John works on Floor 2") don't change during a delivery, so querying multiple times would return the same results. Per-step only makes sense for REFLECT, which synthesizes context-aware guidance.

---

### 4. REFLECT (with inject_once)

**Description:** Queries Hindsight's reflect API once at the start. Returns an LLM-synthesized answer rather than raw facts.

**Memory Query Mode:** `inject_once`

**Behavior:**
1. Before delivery starts, system queries reflect API
2. Hindsight synthesizes a response from relevant facts
3. Synthesized response is injected into system prompt

**Example:**
```
System queries reflect: "Where does John Smith work?"
Hindsight synthesizes: "Based on past deliveries, John Smith works at TechCorp
  which is located on Floor 2, front side of the building. The most efficient
  route from the entrance is to go up one floor and you'll find TechCorp there."
Agent receives this guidance and navigates efficiently
```

**Difference from Recall:** Reflect provides contextual, synthesized guidance. Recall provides raw facts that the agent must interpret.

---

### 4b. REFLECT (with per_step)

**Description:** Queries Hindsight's reflect API before every LLM call with full delivery context.

**Memory Query Mode:** `per_step`

**Context Passed:** The query includes the **full delivery history**:
- Current location (e.g., "I am at Floor 2 Front")
- Recipient name
- Actions taken so far (e.g., "Action: go_up")
- Observations made (e.g., "Observed: Floor 2 has TechCorp, DataCorp")

This allows reflect to synthesize context-aware guidance like "You already checked Floor 1, try Floor 2 instead."

**Behavior:**
1. Before each step, system queries reflect with current location + delivery progress
2. Hindsight synthesizes guidance based on what the agent has tried and where they are
3. Guidance is injected as: `"Memory guidance: {synthesized_response}"`

**Example:**
```
Step 1 (at Floor 1 Front):
  Query: "How do I reach John Smith?
          Context: I am at Floor 1 Front. Delivering to John Smith."
  Hindsight: "Go up to Floor 2. John works at TechCorp on the front side."

Step 2 (at Floor 2 Front):
  Query: "How do I reach John Smith?
          Context: I am at Floor 2 Front. Delivering to John Smith.
          Delivery progress: Action: go_up, Observed: Floor 2 has TechCorp..."
  Hindsight: "You're on the right floor. TechCorp should be right here. Deliver the package."
```

**Why per_step works for REFLECT but not RECALL:** Reflect uses an LLM to synthesize answers, so it can incorporate the current context (location, what's been tried) to give more relevant guidance. Recall just returns static facts that don't change based on context.

---

### 5. HINDSIGHT_MM (Mental Models with Wait)

**Description:** Uses Hindsight with mental model consolidation. After each delivery, waits for mental models to form before the next delivery.

**Bank Setup:**
- Bank has a **mission** that guides mental model formation:
  ```
  You are a delivery agent navigating a building to deliver packages.
  Your goal is to learn and remember:
  - Employee locations: which floor and side each employee works at
  - Building layout: how floors are organized
  - Optimal delivery paths
  ```

**Query Type:** Can use either `recall` or `reflect` (controlled by `mm_query_type`)

**Behavior:**
1. After delivery completes, facts are retained to Hindsight
2. System waits for `pending_consolidation` to reach 0
3. Mental models form based on the mission (e.g., "Building Layout Model", "Employee Directory")
4. Next delivery queries include mental model knowledge

**Example:**
```
Delivery 1: Deliver to John Smith → Success
  Retain: "John Smith works at TechCorp on Floor 2 Front"
  Wait for consolidation...
  Mental model forms: "Employee Directory: John Smith → Floor 2 Front (TechCorp)"

Delivery 2: Deliver to John Smith
  Query includes mental model knowledge
  Agent navigates directly (mental model provides structured knowledge)
```

**mm_query_type options:**
- `recall`: Query returns raw facts + mental model facts (inject_once only)
- `reflect`: Query returns LLM-synthesized response incorporating mental models (supports per_step)

**Note on memory_query_mode:** Per-step injection only works when `mm_query_type="reflect"`. If using `mm_query_type="recall"`, only `inject_once` is effective (per_step falls back to inject_once behavior).

---

### 6. HINDSIGHT_MM_NOWAIT (Mental Models without Wait)

**Description:** Same as HINDSIGHT_MM but does not wait for mental model consolidation after each delivery.

**Behavior:**
1. After delivery, facts are retained to Hindsight
2. System immediately proceeds to next delivery (no wait)
3. Mental models form asynchronously in the background
4. Early deliveries may not benefit from mental models; later ones will

**Example:**
```
Delivery 1: Deliver to John → Success, retain facts, continue immediately
Delivery 2: Deliver to Sarah → Mental models still forming, uses raw facts
Delivery 3: Deliver to John → Mental models now available, faster navigation
```

**Trade-off:** Lower latency between deliveries, but mental models may not be ready when queried.

---

## Memory Query Mode Summary

| Mode | inject_once | per_step | both |
|------|-------------|----------|------|
| Effect | Query once at start, inject into system prompt | Query before each LLM call (REFLECT only) | Both combined (REFLECT only) |
| Latency | Low (1 query per delivery) | High (1 query per step) | Highest |
| Guidance | Static for entire delivery | Dynamic, context-aware | Dynamic with initial context |
| Applies to | All modes | REFLECT modes only | REFLECT modes only |

**Important:** `per_step` and `both` only have effect when using REFLECT (either `mode: "reflect"` or MM modes with `mm_query_type: "reflect"`). For RECALL modes, only `inject_once` is effective because recall returns static facts that don't benefit from repeated queries.

---

## Configuration Examples

### Example 1: Simple Recall
```json
{
  "mode": "recall",
  "memory_query_mode": "inject_once"
}
```
Query Hindsight once at start, inject raw facts into prompt.

### Example 2: Per-Step Reflect
```json
{
  "mode": "reflect",
  "memory_query_mode": "per_step"
}
```
Query Hindsight reflect API before every step with current context. Note: `mm_query_type` is only used for MM modes.

### Example 3: Mental Models with Reflect
```json
{
  "mode": "hindsight_mm",
  "memory_query_mode": "inject_once",
  "mm_query_type": "reflect"
}
```
Wait for mental models, then query reflect once at start. Mental models provide structured knowledge that reflect synthesizes into guidance.

### Example 4: Mental Models Per-Step with Reflect (NoWait)
```json
{
  "mode": "hindsight_mm_nowait",
  "memory_query_mode": "per_step",
  "mm_query_type": "reflect"
}
```
Don't wait for consolidation, query reflect before each step with full delivery context. Good for complex navigation where context-aware guidance helps.

### Example 5: Mental Models with Recall (NoWait)
```json
{
  "mode": "hindsight_mm_nowait",
  "memory_query_mode": "inject_once",
  "mm_query_type": "recall"
}
```
Don't wait for consolidation, query recall once at start. Good for high-throughput scenarios with simple navigation.

---

## Storage Behavior

### Hindsight Modes (recall, reflect, hindsight_mm, hindsight_mm_nowait)

Store delivery results to Hindsight after completion:

```
Content: "Delivery to John Smith at TechCorp (Floor 2, Front).
         Started at: Floor 1 Front. Steps: 3. Outcome: SUCCESS
         Actions: go_up → go_to_front → deliver"
Context: "delivery:John Smith:success"
```

For MM modes, this retained content triggers mental model consolidation based on the bank mission.

### Filesystem Mode

Stores notes locally (in-memory) via LLM processing:

```
LLM Input: "Current notes: ... Recent delivery: SUCCESS to John Smith..."
LLM Output: "John Smith - Floor 2 Front, TechCorp
            Sarah Kim - Floor 3 Back, DataCorp"
```

Notes persist between deliveries but are not sent to Hindsight.

### No Memory Mode

Nothing is stored. Each delivery starts fresh.
