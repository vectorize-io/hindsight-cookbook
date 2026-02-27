#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Load .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8002}" --ws wsproto --reload
