#!/bin/bash

# Memory Approaches Comparison Demo - Run Script
# Compares: No Memory vs Full Conversation History vs Hindsight Memory
# Usage: ./run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "  Memory Approaches Comparison Demo"
echo "=================================================="
echo ""

# Parse arguments
for arg in "$@"; do
    case $arg in
        --help|-h)
            echo "Usage: ./run.sh"
            echo ""
            echo "This demo compares three memory approaches:"
            echo "  1. No Memory - Each query is independent (baseline)"
            echo "  2. Full Conversation History - Pass entire conversation (truncated)"
            echo "  3. Hindsight Memory - Intelligent semantic memory retrieval"
            echo ""
            echo "Prerequisites:"
            echo "  - Python 3.10+"
            echo "  - Hindsight server running (see below)"
            echo "  - At least one LLM API key (e.g., OPENAI_API_KEY)"
            echo ""
            echo "To start Hindsight server:"
            echo "  docker run -d -p 8888:8888 -p 9999:9999 \\"
            echo "    -e HINDSIGHT_API_LLM_PROVIDER=openai \\"
            echo "    -e HINDSIGHT_API_LLM_API_KEY=\$OPENAI_API_KEY \\"
            echo "    ghcr.io/vectorize-io/hindsight:latest"
            echo ""
            exit 0
            ;;
    esac
done

# Check for API keys
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY not set"
    echo "   Set it with: export OPENAI_API_KEY=your-key"
    echo ""
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Check/install core dependencies
echo "Checking core dependencies..."

if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "   Installing streamlit..."
    pip install streamlit
fi

if ! python3 -c "import litellm" 2>/dev/null; then
    echo "   Installing litellm..."
    pip install litellm
fi

# Check Hindsight packages
echo ""
echo "Checking Hindsight packages..."

# Hindsight client (required)
if python3 -c "import hindsight_client" 2>/dev/null; then
    echo "   hindsight-client installed"
else
    echo "   hindsight-client not installed"
    echo "   Installing from PyPI..."
    pip install hindsight-client
fi

# Hindsight LiteLLM (required)
if python3 -c "import hindsight_litellm" 2>/dev/null; then
    echo "   hindsight-litellm installed"
else
    echo "   hindsight-litellm not installed"
    echo "   Installing from PyPI..."
    pip install hindsight-litellm
fi

# Check if Hindsight is running
HINDSIGHT_URL="${HINDSIGHT_URL:-http://localhost:8888}"

echo ""
echo "Checking Hindsight server: $HINDSIGHT_URL"
if curl -s "$HINDSIGHT_URL/health" > /dev/null 2>&1; then
    echo "   Server is running"
else
    echo "   Hindsight server not responding at $HINDSIGHT_URL"
    echo ""
    echo "   Please start Hindsight first with Docker:"
    echo "     docker run -d -p 8888:8888 -p 9999:9999 \\"
    echo "       -e HINDSIGHT_API_LLM_PROVIDER=openai \\"
    echo "       -e HINDSIGHT_API_LLM_API_KEY=\$OPENAI_API_KEY \\"
    echo "       ghcr.io/vectorize-io/hindsight:latest"
    echo ""
    echo "   Or follow the quickstart guide:"
    echo "   https://github.com/vectorize-io/hindsight#quickstart"
    echo ""
    exit 1
fi

# Launch the app
echo ""
echo "Starting Streamlit app..."
echo "   Open http://localhost:8501 in your browser"
echo ""
echo "=================================================="
echo ""

streamlit run app.py --server.port 8501 --server.headless true
