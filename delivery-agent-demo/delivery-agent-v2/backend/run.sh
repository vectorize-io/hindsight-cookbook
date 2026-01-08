#!/bin/bash
# Run the delivery agent backend with wsproto for proper WebSocket handling
cd "$(dirname "$0")"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws wsproto --reload
