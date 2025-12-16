#!/bin/bash

# Development startup script

set -e

echo "🚀 Starting Stance Tracker Development Environment"
echo "=================================================="
echo ""

# Check if Memora is running
echo "Checking Memora API..."
if curl -s http://localhost:8080/ > /dev/null 2>&1; then
    echo "✅ Memora is running at http://localhost:8080"
else
    echo "❌ Memora is not running!"
    echo "Please start Memora first:"
    echo "  cd ../memory-poc"
    echo "  ./scripts/start-server.sh --env local"
    exit 1
fi

echo ""

# Check if PostgreSQL is running
echo "Checking PostgreSQL..."
if docker-compose ps | grep -q "stancetracker-db.*Up"; then
    echo "✅ PostgreSQL is running"
elif pg_isready > /dev/null 2>&1; then
    echo "✅ PostgreSQL is running (local)"
else
    echo "⚠️  PostgreSQL is not running"
    read -p "Start PostgreSQL with Docker? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose up -d
        echo "Waiting for PostgreSQL to be ready..."
        sleep 5
    else
        echo "Please start PostgreSQL manually"
        exit 1
    fi
fi

echo ""

# Check .env file
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    if [ -f .env.local.example ]; then
        read -p "Create .env from .env.local.example? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp .env.local.example .env
            echo "✅ Created .env file"
            echo "⚠️  Please edit .env and add your API keys!"
            exit 0
        fi
    fi
    echo "Please create a .env file with your configuration"
    exit 1
fi

echo "✅ Environment configured"
echo ""

# Start the development server
echo "🚀 Starting Next.js development server..."
echo ""
npm run dev
