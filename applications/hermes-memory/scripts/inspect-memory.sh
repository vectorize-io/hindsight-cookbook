#!/usr/bin/env bash
# inspect-memory.sh — check Hindsight memory status and query memories
#
# Usage:
#   ./scripts/inspect-memory.sh

set -euo pipefail

PROFILE="hermes"
EMBED_CMD="uvx hindsight-embed@latest"

echo "=== Hermes Memory Inspector ==="
echo ""

# Memory provider status
echo "--- Memory Provider Status ---"
if ! hermes memory status; then
  echo ""
  echo "Memory provider not connected. Try:"
  echo "  hermes memory setup"
  exit 1
fi
echo ""

# Check for uvx
if ! command -v uvx &>/dev/null; then
  echo "--- Search Memories ---"
  echo "Error: 'uvx' not found in PATH."
  echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
  echo ""
  echo "Or run this command manually:"
  echo "  uvx hindsight-embed@latest -p $PROFILE memory recall $PROFILE \"<query>\""
  exit 0
fi

# Interactive recall
echo "--- Search Memories ---"
read -rp "Enter a search query (or press Enter to skip): " QUERY

if [[ -n "$QUERY" ]]; then
  echo ""
  $EMBED_CMD -p $PROFILE memory recall $PROFILE "$QUERY" 2>/dev/null || echo "(search failed or no memories found)"
  echo ""
fi

# Offer to open UI
read -rp "Open memory browser UI? [y/N] " OPEN_UI
if [[ "$OPEN_UI" =~ ^[Yy]$ ]]; then
  echo "Opening UI..."
  $EMBED_CMD -p $PROFILE ui
fi
