# Deliveryman Demo - Benchmark Application

This is a benchmark demo for testing Hindsight memory with a delivery agent simulation.

## Project Structure

```
deliveryman-demo/
├── backend/           # FastAPI backend (Python)
│   ├── app/
│   │   ├── main.py           # Main FastAPI app with WebSocket endpoints
│   │   ├── config.py         # Configuration (LLM, Hindsight API URL)
│   │   └── services/
│   │       ├── agent_service.py      # Delivery agent logic
│   │       ├── memory_service.py     # Hindsight integration
│   │       ├── benchmark_service.py  # Benchmark runner
│   │       └── benchmark_charts.py   # Chart generation (matplotlib)
│   ├── building.py    # Building simulation with floors/businesses
│   ├── agent_tools.py # LLM tool definitions
│   └── run.sh         # Start script
├── frontend-benchmark/  # React + Vite benchmark UI
│   └── src/
│       ├── App.tsx              # Main benchmark UI
│       ├── hooks/useWebSocket.ts # WebSocket connection to backend
│       └── game/                # Phaser game visualization
└── results/           # Saved benchmark results (JSON + SVG charts)
```

## Starting the Services

### 1. Hindsight API (Required)
```bash
cd /path/to/hindsight
git checkout benchmark-mm
./scripts/dev/start-api.sh
# Runs on http://localhost:8888
```

### 2. Backend (Port 8000)
**IMPORTANT: Must use `--ws wsproto` flag for WebSocket support!**

```bash
cd backend
./run.sh
# Or manually:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws wsproto --reload
```

Without `--ws wsproto`, WebSocket connections will fail with "400 Bad Request" and error code 1006.

### 3. Frontend Benchmark (Port 5173)
```bash
cd frontend-benchmark
npm run dev
# Runs on http://localhost:5173
```

### 4. Hindsight Control Plane (Optional)
```bash
cd /path/to/hindsight
./scripts/dev/start-control-plane.sh
# Runs on dynamic port (check output)
```

## Configuration

### Backend (.env)
```
HINDSIGHT_API_URL=http://localhost:8888
```

### Hindsight (.env)
```
HINDSIGHT_API_LLM_PROVIDER=groq
HINDSIGHT_API_LLM_MODEL=openai/gpt-oss-120b
HINDSIGHT_API_LLM_API_KEY=<your-api-key>
```

## Benchmark Configuration Options

### Agent Modes

| Mode | Description | Memory Injection | Memory Storage | Mental Models |
|------|-------------|------------------|----------------|---------------|
| `no_memory` | Baseline without Hindsight | ❌ | ❌ | ❌ |
| `filesystem` | Agent manages own notes | ❌ | ❌ (local file) | ❌ |
| `recall` | Raw fact retrieval from Hindsight | ✅ (recall API) | ✅ | ❌ |
| `reflect` | LLM-synthesized memory | ✅ (reflect API) | ✅ | ❌ |
| `hindsight_mm` | Mental models with wait | ✅ | ✅ | ✅ (wait for consolidation) |
| `hindsight_mm_nowait` | Mental models without wait | ✅ | ✅ | ✅ (fire-and-forget) |

### MM Query Type (for hindsight_mm modes)

| Query Type | Description |
|------------|-------------|
| `recall` | Uses raw fact retrieval (faster, returns stored facts directly) |
| `reflect` | Uses LLM synthesis (slower, generates contextual answer from facts) |

### Step Limit Settings

The maximum steps per delivery is calculated dynamically:

```
max_steps = max(minSteps, optimalSteps × stepMultiplier)
```

If `maxSteps` (global) is also set, it acts as a hard cap:
```
final_max = min(calculated_max, maxSteps)
```

| Setting | Default | Description |
|---------|---------|-------------|
| `stepMultiplier` | 5.0 | Multiplier applied to optimal path length |
| `minSteps` | 15 | Floor value - agent always gets at least this many steps |
| `maxSteps` | null | Hard cap (optional) - absolute maximum regardless of calculation |

**Example:**
- Optimal path = 4 steps, stepMultiplier = 5.0, minSteps = 15
- Calculated: max(15, 4 × 5) = max(15, 20) = **20 steps allowed**

### Memory Injection Mode

| Mode | At Start | Per Step | Description |
|------|----------|----------|-------------|
| `inject_once` | ✅ | ❌ | Query memory once before delivery starts |
| `per_step` | ❌ | ✅ | Query memory before each agent step |
| `both` | ✅ | ✅ | Query at start AND before each step |

### Preseed Coverage

Pre-seeds building knowledge into memory before running deliveries:

| Value | Description |
|-------|-------------|
| `0.0` | No preseed (default) - agent learns from scratch |
| `0.5` | 50% of employee locations pre-seeded |
| `1.0` | Full building knowledge pre-seeded |

Preseed generates facts like:
- "John Smith works at TechCorp on floor 2."
- "TechCorp is located on floor 2, front side."
- "The building has 3 floors."

### Other Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `repeatRatio` | 0.4 | Fraction of deliveries that revisit previous recipients |
| `pairedMode` | false | Each office visited exactly 2x (for learning evaluation) |
| `includeBusiness` | "random" | Include business name in package: "always", "never", "random" |
| `waitForConsolidation` | true | Whether to wait for mental model refresh to complete |
| `refreshInterval` | 5 | Trigger mental model refresh every N deliveries (0 = disabled) |

### Bank Mission

The bank mission guides mental model generation. Default mission:
```
You are a delivery agent navigating a building to deliver packages to employees.
Your goal is to learn and remember:
- Employee locations: which floor and side of the building each employee works at
- Building layout: how floors are organized, what businesses are on each floor
- Optimal delivery paths: the fastest routes to reach different employees
- Past delivery outcomes: which deliveries succeeded and which failed
```

## Benchmark Metrics (Eval Parity)

The benchmark tracks these metrics per delivery:

| Metric | Description |
|--------|-------------|
| `steps` | Actual steps taken |
| `optimalSteps` | Minimum possible steps (computed via BFS) |
| `pathEfficiency` | optimal / actual (1.0 = perfect) |
| `tokens` | LLM token usage (prompt, completion, total) |
| `latencyMs` | LLM response time |
| `totalTimeMs` | Total delivery time |
| `apiCalls` | Number of LLM API calls |
| `wrongTurns` | Backtracking/failed moves |
| `path` | Sequence of locations visited |
| `mentalModelCount` | Number of mental models in bank |
| `buildingCoverage` | % of building in mental models |

## API Endpoints

### POST /api/delivery/fast

Run a single delivery in fast-forward mode.

**Request:**
```json
{
  "recipientName": "John Smith",     // Optional, random if null
  "includeBusiness": "random",       // "always" | "never" | "random"
  "model": "openai/gpt-4o",
  "stepMultiplier": 5.0,
  "minSteps": 15,
  "maxSteps": null,                  // Hard cap (optional)
  "memoryQueryMode": "inject_once",  // "inject_once" | "per_step" | "both"
  "waitForConsolidation": true,
  "preseedCoverage": 0.0,
  "mmQueryType": "recall",           // "recall" | "reflect"
  "hindsight": {
    "inject": true,
    "reflect": false,
    "store": true,
    "bankId": "my-bank-id",
    "query": "Where does {recipient} work?",
    "mission": "Custom mission..."
  }
}
```

**Response:**
```json
{
  "success": true,
  "steps": 5,
  "optimalSteps": 3,
  "maxStepsAllowed": 15,
  "pathEfficiency": 0.6,
  "recipientName": "John Smith",
  "tokens": { "prompt": 1200, "completion": 150, "total": 1350 },
  "latencyMs": 850,
  "totalTimeMs": 1200,
  "memoryInjected": true,
  "actions": [...]
}
```

## Benchmark Save Format

Results saved to `backend/results/`:
- `{run_name}.json` - Full results with all configs
- `{run_name}_{mode}_dashboard.svg` - Per-config dashboard chart
- `{run_name}_comparison.svg` - Multi-config comparison chart

## Troubleshooting

### WebSocket Disconnected (Error 1006)
The backend MUST be started with `--ws wsproto`:
```bash
python -m uvicorn app.main:app --ws wsproto --reload
```

### Frontend Shows "Disconnected"
1. Check backend is running on port 8000
2. Check browser console for WebSocket URL (should be `ws://localhost:8000/ws/...`)
3. Restart backend with `--ws wsproto` flag

### Hindsight Connection Issues
1. Verify Hindsight API is running on port 8888
2. Check `backend/.env` has correct `HINDSIGHT_API_URL`
3. Check backend logs for memory bank initialization errors

### Mental Models Not Updating
1. Check `refreshInterval` is > 0
2. Check hindsight logs for consolidation errors
3. The `/consolidate` endpoint may not exist on older hindsight branches

## Development Notes

- Frontend WebSocket connects directly to backend (not proxied through Vite)
- Backend creates separate memory banks per app type (demo/bench) and difficulty
- Mental model refresh interval is configurable per benchmark config
- Bank mission is ALWAYS set when using any hindsight mode (required for mental models)

## Running Tests

```bash
cd backend
python test_configurations.py
```

This runs 10 configuration tests verifying:
1. No Memory Mode - no injection, no storage
2. Filesystem Mode - agent's own notes
3. Recall Mode - memory stored after delivery
4. Reflect Mode - memory stored after delivery
5. Hindsight MM (recall query) - memory stored, mission set
6. Hindsight MM (reflect query) - memory stored, mission set
7. Preseed Coverage - 2 docs stored (preseed + delivery)
8. Memory Injection per_step - memory stored
9. Memory Injection both - memory stored
10. Custom Mission Set - memory stored, mission set
