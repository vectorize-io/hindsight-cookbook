#!/bin/bash

# Delivery Agent Demo Launcher
# This script checks prerequisites and launches the Streamlit app

set -e

echo "=========================================="
echo "  Delivery Agent Demo"
echo "  Hindsight Learning Showcase"
echo "=========================================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python 3.9+ is required (found $python_version)"
    exit 1
fi
echo "✓ Python $python_version"

# Check for .env file
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠ Please edit .env and add your OPENAI_API_KEY"
        exit 1
    fi
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY not set in .env file"
    exit 1
fi
echo "✓ OpenAI API key configured"

# Check Hindsight connectivity
HINDSIGHT_URL="${HINDSIGHT_API_URL:-http://localhost:8888}"
if curl -s "$HINDSIGHT_URL/health" > /dev/null 2>&1; then
    echo "✓ Hindsight API available at $HINDSIGHT_URL"
else
    echo "⚠ Warning: Hindsight API not reachable at $HINDSIGHT_URL"
    echo "  Make sure Hindsight is running:"
    echo "  docker run -p 8888:8888 -p 9999:9999 ghcr.io/vectorize-io/hindsight:latest"
    echo ""
fi

# Install dependencies if needed
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi
echo "✓ Dependencies installed"

echo ""
echo "Starting Delivery Agent Demo..."
echo "=========================================="
echo ""

# Launch Streamlit
streamlit run app.py --server.port 8503
