# How AI Agent Learning Works in the CableConnect Demo

## The Problem: AI Agents That Never Learn

Most AI agent demos are stateless. The agent makes the same mistakes every time because it has no way to accumulate knowledge from human feedback. If a customer service agent offers a $50 credit when company policy caps adjustments at $25, it will make the same mistake on the next customer — and every customer after that.

CableConnect solves this with **Hindsight**, a biomimetic memory system that lets the AI copilot learn from every correction a human gives it. The agent retains feedback as structured memories, consolidates patterns into observations, and builds mental models that guide future behavior. By the third or fourth customer, it stops making the mistakes the CSR already corrected.

This article explains exactly how that learning loop works.

---

## The Demo at a Glance

CableConnect is an AI customer service copilot workstation. The UI is split into two chat panels:

- **Left panel** — A simulated customer conversation. The customer's messages appear on the left. When the CSR approves a suggested response from the copilot, it appears on the right as a sent message.
- **Right panel** — The CSR's conversation with the AI copilot. The copilot analyzes the situation, drafts customer responses, and suggests system actions (credits, dispatches, retention offers). The CSR approves or rejects each suggestion.

The human presenter plays the role of the CSR. The customers are simulated by a separate LLM call. The copilot is the agent under evaluation.

Eight customer scenarios run in sequence. They cover billing inquiries, credit requests, technical support, retention, and outage handling. Some scenarios are deliberately paired so the agent can demonstrate learning: the first scenario in a pair teaches the agent a rule, and the second tests whether it remembers.

---

## The Eight Scenarios

| # | Customer | Category | What Happens |
|---|----------|----------|-------------- |
| 1 | Sarah Johnson | Billing | Asks about her bill. Straightforward — the agent investigates charges and explains them. |
| 2 | Mike Chen | Credit | Internet was out for a week, wants compensation. **Learning Pair A** — the agent may offer too large a credit, and the CSR corrects it to the $25 per-adjustment cap. |
| 3 | Lisa Park | Technical | Slow internet, wants a technician. **Learning Pair B** — the agent may skip diagnostics and jump straight to scheduling a dispatch. The CSR corrects it: always run remote diagnostics first. |
| 4 | James Wilson | Credit | Overcharged $40, wants a correction. **Learning Pair A test** — if the agent learned from scenario 2, it should know the $25 cap and handle this correctly without being corrected. |
| 5 | Maria Garcia | Retention | Wants to cancel. **Learning Pair C** — the agent may offer retention deals to a customer with only 8 months of tenure. The CSR corrects it: retention offers require 24+ months. |
| 6 | David Brown | Retention | Also wants to cancel. **Learning Pair C test** — only 6 months tenure. If the agent learned from scenario 5, it should process the cancellation without offering retention deals. |
| 7 | Amy Rodriguez | Outage | Internet down for 3 days, wants a credit. There's an active outage in her area with automatic credits — the agent should check outage status, not post a manual credit. |
| 8 | Tom Nakamura | Technical | Cable keeps freezing. **Learning Pair B test** — if the agent learned from scenario 3, it should run diagnostics before suggesting a dispatch. |

The learning pairs are the heart of the demo:

- **Pair A** (scenarios 2 → 4): Credit adjustment limits ($25 cap)
- **Pair B** (scenarios 3 → 8): Run diagnostics before dispatch
- **Pair C** (scenarios 5 → 6): Retention eligibility requires 24-month tenure

---

## How the Agent Loop Works

Each scenario follows the same loop:

### 1. Scenario loads

The customer's message arrives. The copilot receives the customer's problem along with account details (name, plan, tenure, area).

### 2. Memory recall (if enabled)

Before the agent makes its first LLM call, the system queries Hindsight for relevant past feedback. This is a `recall()` call — a fast, multi-strategy retrieval that searches across semantic similarity, keyword matching, graph traversal, and temporal relevance simultaneously.

The recall query is tailored to the scenario category. For a billing scenario:

> "How should I communicate with customers? What tone should I use? What jargon should I avoid? How should I investigate billing inquiries? Should I compare past bills? What are the rules for billing adjustments and credits?"

The recalled facts are injected into the system prompt:

```
# What I Remember From Past Interactions
The following is what I've learned from previous CSR feedback.
I must follow these lessons to avoid repeating mistakes:

- CSR rejected my post_adjustment suggestion. Feedback: That's over the $25 limit.
- CSR feedback: Always check the previous bill before responding to billing inquiries.
- CSR feedback: Don't offer further assistance until you've answered the customer's question.
```

### 3. Mental models (always injected)

Regardless of whether recall is enabled, the system always fetches the bank's mental models and injects them into the system prompt. Mental models are consolidated summaries that Hindsight synthesizes from accumulated observations. They're injected under a `# My Knowledge (Mental Models)` section.

More on mental models below.

### 4. Agent reasoning

The copilot makes LLM calls with access to 19 tools. **Lookup tools** (account summary, billing statement, signal test, outage check, etc.) execute automatically — the CSR doesn't need to approve information gathering. **Action tools** (suggest customer response, post credit, schedule dispatch, apply retention offer) pause and wait for CSR approval.

### 5. CSR gate

When the copilot suggests an action, the UI shows approval buttons. The CSR can:

- **Approve** — The action executes. If it's a `suggest_response`, the message appears in the customer chat and the customer simulator generates a reply.
- **Reject with feedback** — The CSR types what was wrong. This feedback goes back into the LLM conversation so the copilot can adjust, AND it gets immediately retained into Hindsight as a memory.

### 6. Rejection hints

The system includes a business rules engine that checks each suggestion against known policies. If the copilot suggests a $50 credit, the engine detects it exceeds the $25 cap and shows a hint to the CSR:

> "That's over our $25 per-adjustment limit. You'd need to cap it at $25 or escalate to a supervisor for the full amount."

The CSR can use this hint as their rejection feedback, modify it, or write their own. The hint system covers credit limits, outage policies, diagnostics-before-dispatch rules, retention tenure requirements, contract ETF disclosures, and more.

### 7. Memory retention

Feedback is stored to Hindsight at two points:

**Immediately on rejection or feedback** — Every time the CSR rejects a suggestion or sends direct feedback, the full context is retained right then. The retained content includes:

```
The conversation between the Customer and the Customer Service Rep was:
  Customer: My internet has been really slow for the past few days.
  CSR: I'll schedule a technician to come take a look.

The assistant performed these tool calls:
  get_account_summary({"account_id": "ACC-1003"}) -> {"name": "Lisa Park", ...}
  check_dispatch_availability({"area": "westend"}) -> {"available_slots": [...]}

The assistant made this suggestion:
  schedule_dispatch({"ticket_id": "TT-0001", "slot_id": "SLOT-WE-01"})

The CSR rejected the suggestion with the following feedback:
  We need to run remote diagnostics first. 70% of issues are fixable remotely.
```

This structured format gives Hindsight rich context about what happened, what was suggested, and why it was wrong. Each feedback retain is tagged with `feedback` for filtering.

**Post-processing at scenario end** — After the scenario resolves, a comprehensive summary of the entire interaction is retained with all conversation turns, all tool calls, all suggestions and their outcomes, and all CSR feedback.

### 8. Mental model refresh

After every 5 scenarios, the system triggers a refresh of all mental models. This re-runs each mental model's source query against the updated observation base, producing fresh consolidated summaries that incorporate recent feedback.

---

## How Hindsight Turns Feedback Into Knowledge

This is where the real complexity lives. Hindsight doesn't just store feedback as text blobs — it processes content through a multi-stage pipeline that transforms raw interaction data into structured, retrievable knowledge.

### Stage 1: Fact Extraction

When the agent calls `retain()` with the structured feedback content, Hindsight's extraction engine analyzes it and produces two types of facts:

- **World facts** — Objective information about the domain. "The credit adjustment limit is $25 per adjustment." "Retention offers require 24 months of tenure." These are statements about how the world works.
- **Experiences** — Events and interactions that happened. "The CSR rejected my suggestion to post a $50 credit." "I was told to run diagnostics before scheduling a dispatch." These capture what occurred and what was learned.

The extraction is guided by the bank's **mission** — a natural language description of the bank's purpose:

> "I am a customer service AI copilot at CableConnect. I learn company policies, billing adjustment limits, dispatch procedures, retention eligibility rules, and outage handling protocols from CSR feedback to make better suggestions over time."

This mission tells the extraction engine to focus on policies, limits, procedures, and rules — not ephemeral details like customer names or ticket numbers.

### Stage 2: Entity Recognition and Graph Construction

Hindsight identifies entities in the extracted facts (people, organizations, concepts, policies) and builds a knowledge graph with four types of connections:

- **Entity connections** — All facts mentioning the same entity are linked
- **Semantic connections** — Facts with similar meaning are linked
- **Temporal connections** — Facts close in time are linked
- **Causal connections** — Cause-effect relationships are tracked

This graph is what powers the multi-strategy recall. When the agent asks about credit limits, graph traversal can follow connections from "credit" to "adjustment" to "$25 cap" to "per-adjustment limit" even if those terms don't appear in the query.

### Stage 3: Observation Consolidation

After facts are stored, Hindsight automatically runs an observation consolidation process in the background. This is the key mechanism that turns individual feedback instances into generalized knowledge.

Observations are synthesized from multiple facts:

| Individual Facts | Consolidated Observation |
|-----------------|-------------------------|
| "CSR rejected $50 credit, said limit is $25" | "The per-adjustment credit limit is $25. Credits above this require supervisor escalation. I should always check this limit before suggesting a credit." |
| "CSR rejected $40 credit, told me about $25 cap" | |
| "CSR approved $25 courtesy credit" | |

Observations evolve as new evidence arrives. If a new fact contradicts an existing observation, the consolidation engine reconciles rather than overwrites — preserving the evolution:

> "Previously understood the credit limit as flexible, but CSR feedback consistently enforces a hard $25 per-adjustment cap with no exceptions at the CSR level."

This is biomimetic — it mirrors how human memory works. You don't remember every individual conversation about a policy. You remember the synthesized understanding, supported by specific examples when you need to verify.

### Stage 4: Mental Models

Mental models sit at the top of Hindsight's knowledge hierarchy. They are pre-computed summaries that answer specific questions about the bank's accumulated knowledge. CableConnect defines four mental models:

**Customer Communication Style**
> "How should I talk to customers? What tone and language does the CSR expect? What jargon should I avoid? How concise should my responses be?"

**Conversation Flow & Resolution**
> "When should I resolve an interaction? What steps must I take before ending? How do I handle follow-up questions? What feedback have CSRs given about wrapping up too early?"

**Investigation & Problem Solving**
> "How thoroughly should I investigate before suggesting a response? What lookups should I do for billing, technical, credit, and retention scenarios? Should I compare past bills? Run diagnostics before dispatch?"

**Policy & Business Rules**
> "What are the credit and adjustment limits? What are the rules for outage credits? When must I run diagnostics before dispatch? What are the retention offer eligibility requirements?"

When a mental model is created, Hindsight runs a reflect operation — an agentic loop that searches mental models, observations, and raw facts to synthesize a comprehensive answer to the source query. The result is stored and used as the highest-priority source in future reflect calls.

When mental models are refreshed, this process runs again with the latest observations, producing updated summaries that incorporate everything the agent has learned since the last refresh. The mental model content is always injected into the agent's system prompt, giving the LLM direct access to the agent's accumulated policy knowledge.

---

## The Recall Pipeline

When the agent needs to remember past feedback, Hindsight's recall runs four search strategies in parallel:

1. **Semantic search** — Understands meaning, not just keywords. "What are the credit rules?" matches facts about "adjustment limits" and "billing caps."
2. **Keyword search (BM25)** — Exact term matching. Ensures "$25" and "dispatch" are found even if semantically distant from the query.
3. **Graph traversal** — Follows entity connections. "Credit policy" → "adjustment" → "$25 limit" → "supervisor escalation."
4. **Temporal search** — Prioritizes recent feedback over older memories.

Results from all four strategies are fused using Reciprocal Rank Fusion (RRF) — facts appearing in multiple strategies rank higher. A cross-encoder neural model re-ranks the final results.

The output is controlled by a token budget, not a result count. The agent specifies how many tokens of memory context it can fit in its prompt, and Hindsight fills that budget with the highest-ranked facts.

---

## The Learning Loop in Practice

Here's what the full learning cycle looks like across two scenarios:

### Scenario 2: Mike Chen asks for outage compensation

1. Agent calls `get_account_summary`, `get_billing_statement`, checks outage status
2. Agent calls `suggest_response` with an empathetic message — CSR approves, sends to customer
3. Agent calls `post_adjustment` for a $50 OUTAGE credit
4. System detects this exceeds the $25 cap, shows hint to CSR
5. CSR rejects: *"That's over our $25 per-adjustment limit."*
6. Rejection feedback immediately retained to Hindsight with full conversation context, tagged `feedback`
7. Agent adjusts, suggests $25 credit instead — CSR approves
8. Conversation continues until customer is satisfied
9. Post-processing retain stores the complete interaction
10. Hindsight extracts facts, identifies entities, builds graph connections
11. Observation consolidation runs in background: synthesizes "$25 credit limit" pattern

### Scenario 4: James Wilson was overcharged $40

1. **Recall fires** — queries Hindsight for credit/adjustment knowledge
2. Returns: *"The per-adjustment credit limit is $25. Credits above this require supervisor escalation."*
3. This is injected into the system prompt
4. Mental models also injected — Policy & Business Rules model may already contain the $25 rule
5. Agent investigates, finds the $40 overcharge
6. Agent suggests `post_adjustment` for $25 (not $40!) — it learned the cap
7. CSR approves — no correction needed this time
8. The agent handles the remaining $15 by explaining escalation options to the customer

The agent learned. Not from hardcoded rules, not from few-shot examples, but from a single human correction that was retained, consolidated into an observation, and recalled at the right moment.

---

## Why This Architecture Matters

### Separation of concerns

The learning system is cleanly separated from the agent logic. The agent service doesn't know how Hindsight works internally — it just calls `retain_async()` to store and `recall_async()` to retrieve. Hindsight handles extraction, consolidation, graph construction, and multi-strategy retrieval autonomously.

### Memories persist across sessions

The memory bank (`cable-connect-demo`) lives on Hindsight Cloud. Restarting the backend doesn't erase memories. Only the explicit "Reset Memory" action (which deletes and re-creates the bank) clears accumulated knowledge.

### Immediate and comprehensive retention

Feedback is stored twice: immediately when it happens (so nothing is lost if the scenario is cancelled) and comprehensively at the end (with full conversation context). The immediate retains have no `document_id` so each creates a separate memory. The post-processing retain uses a scenario-level `document_id` for a clean upsert per scenario.

### Mental models as consolidated knowledge

Mental models bridge the gap between raw facts and actionable guidance. Individual feedback instances ("don't offer more than $25") are useful but scattered. Mental models synthesize them into coherent policy summaries that the agent can follow as guidelines. They refresh periodically, automatically incorporating new observations.

### The CSR is always in control

Every action goes through the CSR gate. The agent never talks to the customer directly or takes system actions unilaterally. This isn't just a safety mechanism — it's the source of learning signal. Every approval validates the agent's behavior. Every rejection teaches it something new.

---

## Technical Stack

- **Backend**: Python, FastAPI, WebSocket (wsproto)
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, Zustand
- **LLM**: GPT-4o via hindsight_litellm completion passthrough
- **Memory**: Hindsight Cloud (`hindsight_client.Hindsight` for retain/recall, `httpx` for bank/mental-model management)
- **Thread safety**: `concurrent.futures.ThreadPoolExecutor` wraps synchronous Hindsight calls in async context

The complete source is in `cable-co/` — roughly 700 lines of backend Python and 1200 lines of frontend TypeScript.
