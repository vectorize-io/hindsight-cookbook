#!/bin/bash
#
# Tool Learning Demo - Launch Script
#
# This script checks dependencies and launches the Streamlit demo.
#
# Usage:
#   ./run.sh
#
# Prerequisites:
#   - Python 3.10+
#   - OPENAI_API_KEY environment variable
#   - Hindsight server running at localhost:8888

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Tool Learning Demo - Hindsight"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Check OpenAI API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}Warning: OPENAI_API_KEY not set${NC}"
    echo "  Set it with: export OPENAI_API_KEY=your-key-here"
else
    echo -e "${GREEN}✓ OPENAI_API_KEY is set${NC}"
fi

# Check and install dependencies
echo ""
echo "Checking dependencies..."

# Check streamlit
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "Installing streamlit..."
    pip install streamlit>=1.28.0
fi
echo -e "${GREEN}✓ streamlit installed${NC}"

# Check litellm
if ! python3 -c "import litellm" 2>/dev/null; then
    echo "Installing litellm..."
    pip install litellm>=1.40.0
fi
echo -e "${GREEN}✓ litellm installed${NC}"

# Check hindsight_client
if ! python3 -c "import hindsight_client" 2>/dev/null; then
    echo "Installing hindsight-client..."
    pip install hindsight-client
fi
echo -e "${GREEN}✓ hindsight-client installed${NC}"

# Check hindsight_litellm
if ! python3 -c "import hindsight_litellm" 2>/dev/null; then
    echo "Installing hindsight-litellm..."
    pip install hindsight-litellm
fi
echo -e "${GREEN}✓ hindsight-litellm installed${NC}"

# Check Hindsight server
echo ""
echo "Checking Hindsight server..."
HINDSIGHT_URL="${HINDSIGHT_URL:-http://localhost:8888}"

if curl -s "${HINDSIGHT_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Hindsight server running at ${HINDSIGHT_URL}${NC}"
else
    echo -e "${YELLOW}Warning: Hindsight server not responding at ${HINDSIGHT_URL}${NC}"
    echo ""
    echo "To start Hindsight with Docker:"
    echo ""
    echo "  docker run -d -p 8888:8888 -p 9999:9999 \\"
    echo "    -e HINDSIGHT_API_LLM_PROVIDER=openai \\"
    echo "    -e HINDSIGHT_API_LLM_API_KEY=\$OPENAI_API_KEY \\"
    echo "    -e HINDSIGHT_API_LLM_MODEL=gpt-4o-mini \\"
    echo "    ghcr.io/vectorize-io/hindsight:latest"
    echo ""
    echo "Or continue anyway and the demo will show an error."
fi

# Launch the app
echo ""
echo "=========================================="
echo "Launching Tool Learning Demo..."
echo "=========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
streamlit run "${SCRIPT_DIR}/app.py" --server.port 8502
