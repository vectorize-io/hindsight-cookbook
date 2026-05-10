#!/usr/bin/env bash
# inspect-memory.sh — browse memories stored by hindsight-openclaw
#
# Usage:
#   ./scripts/inspect-memory.sh

set -euo pipefail

PROFILE="openclaw"
EMBED_CMD="uvx hindsight-embed@latest"

if ! command -v uvx &>/dev/null; then
  echo "Error: 'uvx' not found in PATH."
  echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
  echo ""
  echo "Or run these commands manually:"
  echo "  openclaw plugins list | grep hindsight"
  echo "  tail -f /tmp/openclaw/openclaw-*.log | grep Hindsight"
  exit 1
fi

echo "=== Hindsight Memory Inspector ==="
echo ""

# Daemon status
echo "--- Daemon status ---"
$EMBED_CMD -p $PROFILE daemon status 2>/dev/null || echo "(daemon not running — start with 'openclaw gateway')"
echo ""

# Recent memories
echo "--- Recent memories (bank: $PROFILE) ---"
$EMBED_CMD -p $PROFILE memory list $PROFILE --limit 10 2>/dev/null || echo "(no memories found or daemon not running)"
echo ""

# Interactive recall
echo "--- Search memories ---"
read -rp "Enter a search query (or press Enter to skip): " QUERY

if [[ -n "$QUERY" ]]; then
  echo ""
  $EMBED_CMD -p $PROFILE memory recall $PROFILE "$QUERY" 2>/dev/null || echo "(search failed — is the daemon running?)"
  echo ""
fi

# Offer to open UI
read -rp "Open memory browser UI? [y/N] " OPEN_UI
if [[ "$OPEN_UI" =~ ^[Yy]$ ]]; then
  echo "Opening UI..."
  $EMBED_CMD -p $PROFILE ui
fi
