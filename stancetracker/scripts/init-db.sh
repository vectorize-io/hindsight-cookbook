#!/bin/bash

set -e

DB_NAME=${1:-stancetracker}

echo "Initializing database: $DB_NAME"

# Create database if it doesn't exist
if ! psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "Creating database..."
    createdb $DB_NAME
else
    echo "Database already exists"
fi

# Run schema
echo "Running schema..."
psql -d $DB_NAME -f lib/db/schema.sql

echo "✅ Database initialization complete"
