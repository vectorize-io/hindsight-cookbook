# CableConnect — AI Customer Service Copilot Demo

## Concept

An AI copilot assists a CSR (the presenter) by suggesting responses and actions for simulated customer scenarios. The CSR approves or rejects each suggestion with feedback. The copilot learns from rejections via Hindsight and stops repeating mistakes.

**The CSR is the human presenter.** The customers are simulated. The copilot suggests, the human decides.

## UI Layout — Dual Chat Panels

```
┌─────────────────────────────┬───────────────────────────────┐
│  CUSTOMER CHAT              │  AI COPILOT                   │
│                             │                               │
│  [Account banner]           │  Copilot analysis...          │
│                             │                               │
│  Customer: "My bill..."    │  "I suggest responding:"      │
│                             │  [draft message]              │
│  You: "I'd be happy..."   │  [Send to Customer] [Revise]  │
│                             │                               │
│                             │  "I recommend: Post $25..."   │
│                             │  [Approve] [Reject]           │
│                             │                               │
│                             │  ┌ Agent Knowledge ─────────┐ │
│                             │  │ ✓ Credit limit is $25    │ │
│                             │  └──────────────────────────┘ │
└─────────────────────────────┴───────────────────────────────┘
```

- **Left panel**: Chat between customer and CSR (customer messages + approved responses)
- **Right panel**: Chat between CSR and AI copilot (suggestions, approvals, rejections)
- **Knowledge panel**: Pinned at bottom-right, grows as agent learns

## Project Structure

```
cable-co/
├── backend/
│   ├── requirements.txt
│   ├── run.sh                      # uvicorn startup (port 8002)
│   ├── telecom_data.py             # Domain data: accounts, plans, billing, outages, scenarios
│   ├── agent_tools.py              # 20 tools (lookup + action + suggest_response) + business rule hints
│   └── app/
│       ├── main.py                 # FastAPI app + WebSocket
│       ├── config.py               # port 8002
│       └── services/
│           ├── agent_service.py    # Copilot loop — pauses for CSR approval
│           └── memory_service.py   # Hindsight integration
└── frontend/
    └── src/
        ├── types.ts / stores/sessionStore.ts
        ├── hooks/useWebSocket.ts / useToast.ts
        └── components/
            ├── ControlBar.tsx          # Mode, Next Customer, Reset
            ├── CustomerChat.tsx        # Left: customer ↔ CSR chat
            ├── CopilotChat.tsx         # Right: CSR ↔ copilot chat with approve/reject
            ├── KnowledgePanel.tsx      # Bottom-right: learned rules
            ├── MentalModelsPanel.tsx   # Bottom-right: Hindsight mental models
            └── ToastContainer.tsx
```

## Starting the Services

```bash
cd backend && ./run.sh          # Port 8002
cd frontend && npm run dev      # Port 5173
```

Hindsight API must be running on port 8888 for memory modes.

## Demo Flow

1. Presenter clicks "Next Customer" — simulated customer scenario appears in left panel
2. Copilot analyzes (lookups auto-execute) and suggests a response + action in right panel
3. **Copilot PAUSES** — CSR sees "Send to Customer" / "Approve" / "Reject" buttons
4. CSR sends response (appears in left panel) or rejects with feedback
5. On rejection: feedback sent back to copilot, it adjusts
6. Knowledge panel grows with each rejection
7. In Hindsight mode: copilot recalls past feedback before each new customer

### Key Tool: suggest_response

The copilot uses `suggest_response` to draft messages for the customer. When the CSR clicks "Send to Customer", the message appears in the left panel chat. This makes it clear the copilot is assisting the CSR, not talking to the customer directly.

### Learning Pairs
- **Pair A** (credit limit): #2 then #4 — learns $25 cap
- **Pair B** (diagnostics first): #3 then #8 — learns diagnostics before dispatch
- **Pair C** (retention tenure): #5 then #6 — learns 24-month tenure requirement

## WebSocket Protocol

Server → Client: CONNECTED, SCENARIO_LOADED, AGENT_THINKING, AGENT_LOOKUP,
AGENT_SUGGESTION (with rejectionHint), CSR_APPROVED, CSR_REJECTED,
RESPONSE_SENT (approved suggest_response → left panel),
MEMORY_RECALLED, MEMORY_STORING, MEMORY_STORED, KNOWLEDGE_UPDATED,
MODELS_REFRESHING, MODELS_REFRESHED, SCENARIO_RESOLVED_PREVIEW, SCENARIO_RESOLVED, ERROR

Client → Server: process_next, csr_respond (suggestionId + approved + feedback),
set_mode, reset_memory, cancel
