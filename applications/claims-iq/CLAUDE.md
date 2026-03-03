# ClaimsIQ — Insurance Claims Triage Agent Demo

## Project Structure

```
claims-iq/
├── backend/
│   ├── requirements.txt
│   ├── run.sh                  # uvicorn startup (port 8000)
│   ├── claims_data.py          # Domain data: policies, adjusters, scenarios, validation
│   ├── agent_tools.py          # 7 LLM-callable tools + ClaimProcessingState
│   └── app/
│       ├── main.py             # FastAPI app + WebSocket + REST endpoints
│       ├── config.py           # LLM model, Hindsight URL, ports
│       └── services/
│           ├── agent_service.py    # Agent loop (LLM tool-calling)
│           └── memory_service.py   # Hindsight integration
└── frontend/
    ├── package.json / vite.config.ts / tsconfig.json
    ├── index.html
    └── src/
        ├── main.tsx / App.tsx / index.css
        ├── types.ts
        ├── stores/claimsStore.ts   # Zustand state
        ├── hooks/
        │   ├── useWebSocket.ts     # WS connection + event handling
        │   └── useToast.ts
        └── components/
            ├── ControlBar.tsx      # Mode selector, bank mgmt
            ├── Pipeline.tsx        # Stage progress visualization
            ├── ClaimCard.tsx       # Left panel: claim details
            ├── ActivityLog.tsx     # Center: tool call stream
            ├── MetricsPanel.tsx    # Right: accuracy, steps, rework
            ├── MentalModelsPanel.tsx # Right: mental model viewer
            └── ToastContainer.tsx
```

## Starting the Services

### Backend (Port 8000)
```bash
cd backend && ./run.sh
```
Requires `--ws wsproto` for WebSocket support (included in run.sh).

### Frontend (Port 5173)
```bash
cd frontend && npm install && npm run dev
```

### Hindsight API (Port 8888)
Must be running for memory modes to work.

## Agent Modes

| Mode | Memory Injection | Memory Storage | Mental Models |
|------|-----------------|----------------|---------------|
| `no_memory` | No | No | No |
| `recall` | Raw facts | Yes | No |
| `reflect` | Synthesized | Yes | No |
| `hindsight_mm` | Synthesized | Yes | Yes (auto-refresh) |

## Domain Knowledge

### Policy Coverage Matrix
- **Platinum**: covers everything
- **Gold**: auto, property, liability, water_damage, fire (NOT flood, NOT health)
- **Silver**: auto, property, water_damage only
- **Bronze**: auto only
- **Home Shield**: property, liability, water_damage, flood, fire (NOT auto)
- **Auto Plus**: auto, liability only

Key distinction: water_damage (internal plumbing) vs flood (external water source).

### Adjusters
8 adjusters with specialties and regions. Carlos Rivera (ADJ-007) handles fraud.

### Escalation Rules
- Amount > $50K → senior adjuster required
- Amount > $100K → senior adjuster + manager review
- Fraud indicators → route to Carlos Rivera regardless of type
- Prior fraud flag on claimant → must check prior claims history and escalate to ADJ-007

## WebSocket Protocol

Server events: CONNECTED, CLAIM_RECEIVED, AGENT_THINKING, AGENT_ACTION,
CLAIM_STAGE_UPDATE, MEMORY_INJECTED, MEMORY_STORING, MEMORY_STORED,
MODELS_REFRESHING, MODELS_REFRESHED, CLAIM_RESOLVED, ERROR

Client events: process_claim, cancel, set_mode, reset_memory

## 7 Agent Tools

1. `classify_claim(description)` — categorize the claim (may return ambiguous results)
2. `lookup_policy(policy_id)` — get policy details
3. `check_coverage(policy_type, claim_category)` — verify coverage
4. `check_fraud_indicators(claim_id)` — check fraud risk
5. `check_prior_claims(policy_id)` — check prior claims history and fraud flags
6. `get_adjuster(claim_category, region, severity)` — find adjuster
7. `submit_decision(claim_id, decision, adjuster_id, payout_estimate, justification)` — submit for validation

Optimal path is exactly 7 steps (one per tool). The system prompt is intentionally minimal — the agent must discover the workflow through trial and error.
