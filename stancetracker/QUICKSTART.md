# Quick Start Guide

Get Stance Tracker running in 5 minutes!

## Prerequisites

- Node.js 18+
- PostgreSQL (or use Docker)
- Git

## Step 1: Clone and Install

```bash
# Already in the stancetracker directory
npm install
```

## Step 2: Start Memora

Hindsight is required for the memory system. Start it from the parent directory:

```bash
# Clone and run github.com/vectorize-io/hindsight
./scripts/start-server.sh --env local
```

Verify it's running:
```bash
curl http://localhost:8080/
```

## Step 3: Start PostgreSQL

### Option A: Docker (Recommended)

```bash
cd stancetracker
docker-compose up -d
```

The database will automatically initialize with the schema.

### Option B: Local PostgreSQL

```bash
# Create database
createdb stancetracker

# Run schema
psql -d stancetracker -f lib/db/schema.sql
```

## Step 4: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# Database (if using Docker, this is correct)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/stancetracker

# Hindsight (should be running)
HINDSIGHT_API_URL=http://localhost:8080

# Get your Vectorize API key from https://vectorize.io
VECTORIZE_API_KEY=your_key_here
VECTORIZE_API_URL=https://api.vectorize.io

# Choose your LLM provider
LLM_PROVIDER=openai  # or anthropic, groq
LLM_API_KEY=your_openai_key_here
LLM_MODEL=gpt-4-turbo-preview
```

## Step 5: Run the App

```bash
npm run dev
```

Visit: http://localhost:3000

## Step 6: Create Your First Tracking Session

1. **Location**: Enter "United States", "California", "San Francisco"
2. **Topic**: Enter "Climate Change Policy"
3. **Candidates**: Add some names like "Joe Biden", "Donald Trump"
4. **Time Range**: Set start date to 90 days ago, end date to today
5. **Frequency**: Select "Daily"
6. **Click**: "Start Tracking"

The app will:
- Create a scraper agent in Memora
- Initialize a Vectorize index
- Scrape for content (currently simulated)
- Extract stances using LLM
- Display results on the timeline

## Troubleshooting

### "Failed to connect to Memora"
- Check Hindsight is running: `curl http://localhost:8080/`
- Check HINDSIGHT_API_URL in .env

### "Database connection failed"
- Check PostgreSQL is running: `docker-compose ps` or `pg_isready`
- Verify DATABASE_URL in .env

### "Vectorize API error"
- Check your API key is valid
- Verify you have credits/access

### "LLM API error"
- Check your LLM provider API key
- Verify you have API access and credits

## Next Steps

- Read the full [README.md](README.md) for detailed features
- Check [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
- Explore the Hindsight memory system in `github.com/vectorize-io/hindsight`
- Add real content scrapers to `lib/scraper-agent.ts`

## Quick Commands

```bash
# Start everything
docker-compose up -d              # Start PostgreSQL
# Clone and run github.com/vectorize-io/hindsight && ./scripts/start-server.sh --env local  # Start Memora
npm run dev                       # Start app

# Stop everything
docker-compose down               # Stop PostgreSQL
# Ctrl+C in Hindsight terminal
# Ctrl+C in app terminal

# Reset database
docker-compose down -v            # Remove all data
docker-compose up -d              # Start fresh

# View logs
docker-compose logs -f postgres   # Database logs
npm run dev                       # App logs (includes API logs)
```

## Production Notes

For production deployment:
1. Use managed PostgreSQL (Supabase, AWS RDS, etc.)
2. Deploy Hindsight on a server or cloud platform
3. Use Vercel/Netlify for the Next.js app
4. Set up proper monitoring and logging
5. Configure rate limiting and caching
6. Add authentication if needed

See README.md for full deployment instructions.
