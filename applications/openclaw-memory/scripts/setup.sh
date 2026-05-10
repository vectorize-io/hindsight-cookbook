#!/usr/bin/env bash
# setup.sh — wrapper around hindsight-openclaw-setup
#
# Usage:
#   ./scripts/setup.sh                  # interactive
#   ./scripts/setup.sh --mode cloud     # non-interactive (will prompt for token)
#   ./scripts/setup.sh --help           # full flag list

set -euo pipefail

# Check dependencies
if ! command -v openclaw &>/dev/null; then
  echo "Error: 'openclaw' not found in PATH."
  echo "Install OpenClaw first: https://openclaw.ai"
  exit 1
fi

if ! command -v npx &>/dev/null; then
  echo "Error: 'npx' not found in PATH."
  echo "Install Node.js (https://nodejs.org) and try again."
  exit 1
fi

# Install plugin if not already installed
if ! openclaw plugins list 2>/dev/null | grep -q "hindsight-openclaw"; then
  echo "Installing @vectorize-io/hindsight-openclaw plugin..."
  openclaw plugins install @vectorize-io/hindsight-openclaw
else
  echo "Plugin already installed."
fi

echo ""
echo "Running Hindsight setup wizard..."
echo ""

# Pass all args through to the wizard
npx --package @vectorize-io/hindsight-openclaw hindsight-openclaw-setup "$@"

echo ""
echo "Setup complete. Start OpenClaw with:"
echo ""
echo "  openclaw gateway"
echo ""
echo "After a few conversations, run ./scripts/inspect-memory.sh to see what was stored."
