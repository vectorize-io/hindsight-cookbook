#!/bin/bash

# Run Hindsight experiments

cd "$(dirname "$0")"

# Check for .env
if [ ! -f .env ]; then
    echo "No .env file found. Creating from example..."
    cp .env.example .env
    echo "Please edit .env with your API keys"
    exit 1
fi

# Install dependencies if needed
pip install -q -r requirements.txt

# Run experiments
python run_experiments.py
