#!/bin/bash

set -e

echo "🚀 Stance Tracker Setup Script"
echo "================================"
echo ""

# Check for required tools
echo "Checking prerequisites..."

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm first."
    exit 1
fi

if ! command -v psql &> /dev/null; then
    echo "⚠️  PostgreSQL client (psql) not found. You may need to install PostgreSQL."
fi

echo "✅ Prerequisites check passed"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
npm install
echo "✅ Dependencies installed"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys before running the app"
    echo ""
else
    echo "✅ .env file already exists"
    echo ""
fi

# Database setup
echo "🗄️  Database Setup"
read -p "Do you want to set up the database now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter database name (default: stancetracker): " DB_NAME
    DB_NAME=${DB_NAME:-stancetracker}

    # Check if database exists
    if psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
        echo "⚠️  Database '$DB_NAME' already exists"
        read -p "Do you want to recreate it? This will DELETE all data! (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Dropping database..."
            dropdb $DB_NAME
            echo "Creating database..."
            createdb $DB_NAME
        fi
    else
        echo "Creating database..."
        createdb $DB_NAME
    fi

    echo "Running schema..."
    psql -d $DB_NAME -f lib/db/schema.sql
    echo "✅ Database setup complete"
else
    echo "⏭️  Skipping database setup"
fi

echo ""
echo "🎉 Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Make sure Memora is running: cd ../memory-poc && ./scripts/start-server.sh --env local"
echo "2. Edit .env and add your API keys"
echo "3. Run the development server: npm run dev"
echo "4. Visit http://localhost:3000"
echo ""
