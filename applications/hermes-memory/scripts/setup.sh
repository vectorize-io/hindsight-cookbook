#!/usr/bin/env bash
# setup.sh — configure Hindsight memory provider for Hermes
#
# Usage:
#   ./scripts/setup.sh

set -euo pipefail

if ! command -v hermes &>/dev/null; then
  echo "Error: 'hermes' not found in PATH."
  echo "Install Hermes first: https://github.com/NousResearch/hermes-agent"
  exit 1
fi

echo "=== Hermes + Hindsight Memory Setup ==="
echo ""

# Suggest disabling built-in memory tool
echo "Hermes has a built-in markdown-based memory tool."
echo "Disabling it prevents the LLM from preferring it over Hindsight:"
echo ""
read -rp "Disable Hermes's built-in memory tool? [Y/n] " DISABLE_MEMORY
if [[ ! "$DISABLE_MEMORY" =~ ^[Nn]$ ]]; then
  echo "Running: hermes tools disable memory"
  hermes tools disable memory
  echo ""
fi

# Run setup wizard
echo "Running Hindsight setup wizard..."
echo ""
hermes memory setup

echo ""
echo "Setup complete. Verifying connection..."
echo ""

if hermes memory status; then
  echo ""
  echo "✓ Hindsight memory is connected and ready."
  echo ""
  echo "Next steps:"
  echo "  1. Start Hermes:      hermes"
  echo "  2. Have a conversation"
  echo "  3. Exit and restart:  hermes"
  echo "  4. Ask about your memories — they persist across sessions!"
  echo ""
else
  echo ""
  echo "✗ Health check failed. Check your configuration:"
  echo "   cat ~/.hermes/.env | grep HINDSIGHT"
  echo ""
fi
