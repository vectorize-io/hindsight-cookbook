# Stance Tracker Architecture

## Overview

Stance Tracker is a sophisticated AI-powered application that demonstrates advanced memory system capabilities through real-world political stance tracking. It combines multiple cutting-edge technologies to create a comprehensive solution for monitoring and analyzing how political figures' positions evolve over time.

## Core Components

### 1. Memory System (Memora)

The application extensively leverages the Hindsight memory system from `github.com/vectorize-io/hindsight`, utilizing all three memory networks:

#### World Network
- **Purpose**: Stores factual information about candidates, events, and statements
- **Usage**:
  - Candidate biographical information
  - Public statements and speeches
  - News articles and media coverage
  - Event attendance and participation
- **Example**: "Senator Smith spoke at climate rally in San Francisco on March 15, 2024"

#### Agent Network
- **Purpose**: Tracks scraper agents' activities and discoveries
- **Usage**:
  - Content scraping activities
  - Source discovery and indexing
  - Processing status and errors
  - Agent reasoning and decision-making
- **Example**: "Agent discovered 15 new sources for Candidate X on Topic Y"

#### Opinion Network
- **Purpose**: Stores candidate stances as opinions with confidence scores
- **Usage**:
  - Extracted stances with confidence levels
  - Position changes and evolution
  - Uncertainty and ambiguity tracking
  - Historical stance comparison
- **Example**: "Candidate X supports renewable energy (confidence: 0.85)"

#### Memory Features Utilized

1. **Temporal Search**: Query stances within specific time windows
   - "What was Candidate X's position on immigration last spring?"
   - Time-based filtering of references and stances

2. **Entity Resolution**: Automatic linking across mentions
   - Candidate name variations (e.g., "Sen. Smith" vs "Senator Jane Smith")
   - Topic synonyms and related concepts
   - Geographic entity normalization

3. **Spreading Activation**: Graph-based memory retrieval
   - Discover related stances and topics
   - Find indirect connections between candidates
   - Explore stance networks

4. **Personality Framework**: Agent characteristics
   - Scraper agents have high openness (diverse sources)
   - High conscientiousness (thorough collection)
   - Low bias strength (objective analysis)

### 2. RAG System (Vectorize)

The Retrieval-Augmented Generation pipeline combines multiple search strategies:

#### Vector Search (Vectorize API)
- **Embeddings**: Content embedded using state-of-the-art models
- **Semantic Similarity**: Find conceptually related content
- **Scalability**: Efficient search over millions of documents
- **Metadata Filtering**: Filter by date, source type, candidate, etc.

#### Hybrid Retrieval Strategy

```
Query → [Vector Search + Hindsight Semantic + Hindsight Temporal + Hindsight Graph]
     → Merge Results → Re-rank → MMR Diversification → Top K
```

**Re-ranking Factors**:
- Vector similarity score (40%)
- Hindsight semantic relevance (30%)
- Temporal recency (20%)
- Source credibility (10%)

**Source Credibility Weights**:
- Official speeches: 1.0
- Press releases: 0.95
- Interviews: 0.9
- News articles: 0.8
- Social media: 0.6

### 3. Content Scraping System

#### Dual-Mode Architecture

The system supports two scraping modes configured per session:

**Mode 1: Direct Web Scraping** (Recommended)
- Primary scraper using Tavily API
- Real-time web search with high-quality results
- Fallback to custom scrapers for specific regions
- Optimized for Canadian news sources (CBC, CTV, Ottawa Citizen, Global News)
- Returns full article content with metadata
- No setup required - works out of the box

**Mode 2: Vectorize Pipelines**
- Uses pre-configured Vectorize data pipelines
- Requires pipeline setup and configuration
- Ideal for large-scale, pre-indexed datasets
- Better for recurring queries over static corpuses

#### Scraper Agents

Each tracking session gets a dedicated scraper agent with:
- Unique agent ID: `scraper_{session_id}`
- Personality optimized for discovery
- Background knowledge of tracking task
- Memory of all scraping activities
- Mode-specific behavior

#### Tavily Integration

The Tavily API integration provides:
- Advanced web search with `search_depth: 'advanced'`
- Raw content extraction for full articles
- Publication date extraction
- Automatic quality filtering
- High confidence scores (typically 0.85-0.90)

Example search query format:
```
"{candidate}" "{topic}" (stance OR position OR opinion OR policy OR statement)
```

#### Scraping Pipeline

**Direct Web Scraping Flow:**
```
1. Generate search queries (candidate + topic + location)
2. Query Tavily API (or fallback scrapers)
3. Extract full content and metadata
4. Convert to Reference objects
5. Store in Hindsight (semantic memory)
6. Record scraping activity (agent memory)
7. Return references for stance extraction
```

**Vectorize Pipeline Flow:**
```
1. Query configured Vectorize pipelines
2. Retrieve pre-indexed documents
3. Deduplicate by relevancy score
4. Convert to Reference objects
5. Store in Hindsight (semantic memory)
6. Record scraping activity (agent memory)
7. Return references for stance extraction
```

### 4. Stance Extraction Pipeline

#### LLM-Powered Analysis

The system uses configurable LLM providers (OpenAI, Anthropic, Groq) for:

1. **Stance Extraction**
   - Input: Candidate, topic, and relevant references
   - Output: Detailed stance, summary, confidence score
   - Temperature: 0.3 (for consistency)
   - JSON mode: Structured output

2. **Change Detection**
   - Input: Previous stance vs. current stance
   - Output: Change flag, description, magnitude (0-1)
   - Temperature: 0.2 (for precision)

#### Confidence Scoring

Factors affecting confidence:
- Source quality and credibility
- Consistency across multiple sources
- Directness of quotes vs. interpretation
- Recency of information
- Clarity of position statements

### 5. Database Schema

#### PostgreSQL Tables

**tracking_sessions**
- Session configuration and metadata
- Geographic targeting (country, state, city)
- Candidate list and topic
- Time range and frequency settings
- **scraping_mode**: 'direct_web' | 'vectorize_pipelines'
- vectorize_pipeline_ids: Array of pipeline IDs (when using Vectorize mode)
- Status tracking (active, paused, completed)

**stance_points**
- Individual stance snapshots
- Timestamp and confidence
- Link to Hindsight opinion ID
- Change detection metadata

**references**
- Source materials
- URLs, titles, excerpts
- Publication dates
- Vectorize IDs for lookup

**stance_point_references**
- Many-to-many relationship
- Links stances to sources

**scraper_configs**
- Agent configurations
- Source lists and search queries
- Enable/disable flags

### 6. Scheduling System

#### Job Scheduler

Built on node-cron with:
- Per-session scheduling
- Configurable frequencies (hourly/daily/weekly)
- Automatic session checking
- Error handling and retry logic

#### Execution Flow

```
Cron Trigger → Check Active Sessions → For Each Session:
  → Initialize Pipeline
  → Process Each Candidate
    → Scrape Content
    → Retrieve from RAG
    → Extract Stance
    → Detect Changes
    → Store Results
    → Update Memora
  → Update Session Timestamp
```

## Data Flow

### Session Creation Flow

```
User Input → Create Session (DB)
         → Initialize Scraper Agent (Memora)
         → Create Vectorize Index
         → Schedule Cron Job
         → Initial Processing Run
```

### Stance Processing Flow

```
1. Query Builder: Generate search queries from candidate + topic
2. Content Scraper: Fetch from multiple sources
3. Vectorize Indexing: Embed and store content
4. Hindsight Storage: Store as world facts and agent activities
5. RAG Retrieval: Multi-strategy search for relevant content
6. LLM Extraction: Analyze references and extract stance
7. Change Detection: Compare with previous stance
8. Hindsight Opinion: Store as opinion in opinion network
9. Database Storage: Save stance point and references
10. Timeline Update: Refresh visualization data
```

### Query Flow

```
UI Request → API Route → Database Query
         → Hydrate References
         → Format for Recharts
         → Return Timeline Data
```

## Frontend Architecture

### Component Hierarchy

```
App (page.tsx)
├── ScrapingModeSelector (Radio buttons)
├── LocationInput
├── TopicInput
├── CandidateInput
├── TimeSettings
├── ProcessingStatusBar (Real-time progress)
└── StanceTimeline
    ├── LineChart (Recharts)
    │   ├── Two-layer Dots (Candidate + Position)
    │   └── Connected Lines (with nulls)
    ├── CustomTooltip (Enhanced with position)
    ├── PositionLegend (Support/Oppose/Neutral)
    └── SourcesPanel
        └── Reference Links
```

### State Management

- **Form State**: Location, topic, candidates, time range, scraping mode
- **Session State**: Active tracking session ID and configuration
- **Timeline Data**: Fetched stance points with references
- **Processing Status**: Real-time tracking of candidate processing
  - Current candidate being analyzed
  - Progress percentage (currentIndex / total)
  - Animated progress bar
  - Auto-hide after completion
- **UI State**: Loading, messages, selected points, hover states

### Visualization Features

#### Stance Position Color Coding

The timeline uses a dual-color system to show both candidate identity and stance position:

**Two-Layer Dot System:**
- **Outer Ring** (10px radius): Candidate color for identification
  - Blue, Red, Green, Orange, Purple, Cyan (rotating)
- **Inner Dot** (6px radius): Position color based on keyword analysis
  - Green: Supports the topic/issue
  - Red: Opposes the topic/issue
  - Gray: Neutral or unclear position

**Position Determination Algorithm:**
```typescript
function determineStancePosition(stance: string, summary: string): 'support' | 'oppose' | 'neutral' {
  const text = `${stance} ${summary}`.toLowerCase();

  const supportKeywords = ['support', 'favor', 'advocate', 'endorse', 'promote',
                          'champion', 'back', 'approve', 'agree', 'pro-', 'for the'];
  const opposeKeywords = ['oppose', 'against', 'reject', 'resist', 'condemn',
                         'criticize', 'denounce', 'disapprove', 'anti-',
                         'vote against', 'voted against'];

  const supportScore = supportKeywords.filter(kw => text.includes(kw)).length;
  const opposeScore = opposeKeywords.filter(kw => text.includes(kw)).length;

  if (supportScore > opposeScore && supportScore > 0) return 'support';
  if (opposeScore > supportScore && opposeScore > 0) return 'oppose';
  return 'neutral';
}
```

#### Timeline Data Structure

To ensure line connectivity across sparse data points, the timeline creates a complete grid:

```typescript
// Transform sparse data into complete time series
const uniqueTimestamps = Array.from(new Set(allPoints.map(p => p.timestamp)));
const uniqueCandidates = Array.from(new Set(allPoints.map(p => p.candidate)));

const timeSeriesData = uniqueTimestamps.map(timestamp => {
  const entry: any = { timestamp, dateLabel };

  // Add data for each candidate (null if no data at this timestamp)
  uniqueCandidates.forEach(candidate => {
    const point = allPoints.find(p => p.timestamp === timestamp && p.candidate === candidate);
    entry[`${candidate}_confidence`] = point ? point.confidence : null;
    entry[`${candidate}_data`] = point || null;
  });

  return entry;
});

// Line component uses connectNulls to draw across gaps
<Line connectNulls={true} ... />
```

This ensures:
- Lines are visible between actual data points
- Each candidate has a consistent presence on the timeline
- Missing data doesn't break line continuity

#### Real-Time Processing Status

When "Run Now" is clicked, a status bar appears showing:
- Which candidate is currently being processed
- Progress indicator (e.g., "2 of 3")
- Percentage complete
- Animated progress bar
- Auto-dismisses after 2 seconds when complete

```typescript
interface ProcessingStatus {
  isProcessing: boolean;
  currentCandidate: string;
  currentIndex: number;  // 1-indexed
  total: number;
}
```

### API Integration

- RESTful endpoints via Next.js API routes
- Server-side processing for scraping and LLM calls
- Client-side data fetching with loading states
- Real-time status updates during candidate processing
- Optimistic UI updates for better UX

## Scalability Considerations

### Horizontal Scaling

- **Stateless API**: All state in DB and external services
- **Separate Services**: Memora, Vectorize, DB can scale independently
- **Session Isolation**: Each session has isolated resources

### Performance Optimizations

- **Caching**: Hindsight has 15-minute cache for repeated queries
- **Batch Processing**: Process multiple candidates in parallel
- **Lazy Loading**: Timeline loads on-demand
- **Database Indexing**: Optimized queries with proper indexes

### Resource Management

- **Connection Pooling**: PostgreSQL connection pool (max 20)
- **Rate Limiting**: Respect API rate limits
- **Timeout Handling**: 2-second connection timeout
- **Error Recovery**: Graceful degradation on failures

## Security Considerations

### API Keys

- Environment variables for sensitive data
- No keys in client-side code
- Separate keys for dev/prod

### Data Privacy

- No PII collection beyond necessary tracking data
- Source attribution for transparency
- User consent for data collection

### Input Validation

- Zod schemas for type safety
- SQL parameterization (no injection)
- API request validation

## Migration Path

### Local → Supabase

1. Export PostgreSQL schema
2. Create Supabase project
3. Import schema via SQL editor
4. Update DATABASE_URL
5. Test connections
6. Deploy

### Extension Points

- **New LLM Providers**: Add methods to llm-client.ts
- **Custom Scrapers**: Extend scraper-agent.ts
- **Additional Memory Networks**: Leverage Memora's extensibility
- **Custom Visualizations**: Add components using Recharts
- **Export Formats**: Add API routes for CSV/PDF/JSON export

## Performance Metrics

### Key Metrics to Monitor

- Stance extraction accuracy
- Source diversity and coverage
- Change detection precision
- Query response times
- Scraping success rates
- Memory retrieval relevance
- User engagement metrics

### Benchmarking

Use Memora's built-in benchmarking:
- LoComo (conversational memory)
- LongMemEval (long-term retention)
- Custom stance tracking metrics

## Future Enhancements

### Planned Features

1. **Real-time Monitoring**: WebSocket updates for live stance changes
2. **Comparative Analysis**: Side-by-side candidate comparison
3. **Predictive Analytics**: ML models for stance prediction
4. **Multi-language Support**: International candidate tracking
5. **Mobile App**: Native iOS/Android applications
6. **Public API**: Third-party integrations
7. **Webhook Notifications**: Alerts for significant changes
8. **Advanced Visualizations**: Network graphs, heat maps, sentiment analysis

### Research Opportunities

- Stance consistency scoring
- Influence pattern detection
- Topic clustering and relationships
- Temporal prediction models
- Cross-candidate network analysis
- Media bias detection
- Source reliability scoring
