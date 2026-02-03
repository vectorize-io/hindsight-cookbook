#!/bin/bash
# Run the delivery agent backend with wsproto for proper WebSocket handling
cd "$(dirname "$0")"

# Use BACKEND_PORT env var or default to 8000
PORT=${BACKEND_PORT:-8000}

python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --ws wsproto --reload
