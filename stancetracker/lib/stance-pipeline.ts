import { ScraperAgent } from './scraper-agent';
import { RAGSystem } from './rag-system';
import { StanceExtractor } from './stance-extractor';
import { hindsightClient } from './hindsight-client';
import { vectorizeClient } from './vectorize-client';
import { newsSourceDiscovery, NewsSource } from './news-source-discovery';
import { query, queryOne } from './db';
import { StancePoint, Reference, Location } from '@/types';

export class StancePipeline {
  private scraperAgent: ScraperAgent;
  private ragSystem: RAGSystem;
  private stanceExtractor: StanceExtractor;
  private sessionId: string;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
    this.scraperAgent = new ScraperAgent(sessionId);
    this.ragSystem = new RAGSystem(sessionId);
    this.stanceExtractor = new StanceExtractor(sessionId);
  }

  async initialize(
    candidate: string,
    topic: string,
    location: Location
  ): Promise<void> {
    console.log(`\n====================================`);
    console.log(`Initializing Stance Pipeline`);
    console.log(`Candidate: ${candidate}`);
    console.log(`Topic: ${topic}`);
    console.log(`Location: ${JSON.stringify(location)}`);
    console.log(`====================================\n`);

    await this.scraperAgent.initialize(candidate, topic, location);

    // Discover and set up Vectorize pipelines for supplemental data
    await this.discoverRelevantSources(candidate, topic, location);

    console.log(`Stance pipeline initialized successfully\n`);
  }

  private async discoverRelevantSources(
    candidate: string,
    topic: string,
    location: Location
  ): Promise<void> {
    try {
      console.log(`\n--- Discovering News Sources ---`);
      console.log(`Discovering news sources for ${topic} in`, location);

      const newsSources = await newsSourceDiscovery.discoverNewsSources(
        topic,
        location,
        3 // Get top 3 sources
      );

      if (newsSources.length === 0) {
        console.log('No news sources discovered');
        return;
      }

      console.log(`Discovered ${newsSources.length} relevant news sources:`);
      newsSources.forEach(source => {
        console.log(`  - ${source.name} (${source.url}) - relevance: ${source.relevance_score}/10`);
      });

      // Create Vectorize pipelines for each news source
      await this.createPipelinesForSources(newsSources, candidate, topic);
    } catch (error) {
      console.log('News source discovery skipped:', error instanceof Error ? error.message : error);
    }
  }

  private async createPipelinesForSources(
    newsSources: NewsSource[],
    candidate: string,
    topic: string
  ): Promise<void> {
    console.log(`\n--- Creating Vectorize Pipelines ---`);

    // Check if required API key is available
    const openaiApiKey = process.env.OPENAI_API_KEY || process.env.LLM_API_KEY;

    if (!openaiApiKey) {
      console.log('Skipping pipeline creation: Missing required API key (OPENAI_API_KEY or LLM_API_KEY)');
      return;
    }

    const pipelineIds: string[] = [];

    for (const source of newsSources) {
      try {
        console.log(`Creating pipeline for ${source.name}...`);

        // Create a unique pipeline name
        const pipelineName = `${this.sessionId}-${source.name.toLowerCase().replace(/\s+/g, '-')}-${Date.now()}`;

        // Create the complete pipeline with built-in WEB_CRAWLER source and VECTORIZE destination
        const result = await vectorizeClient.createCompletePipeline({
          name: pipelineName,
          sourceUrls: [source.url],
          openaiApiKey,
          crawlerConfig: {
            maxDepth: 3,
            maxUrls: 100,
            minTimeBetweenRequests: 1000,
          },
          schedule: {
            enabled: true,
            cronExpression: '0 */6 * * *', // Run every 6 hours
          },
        });

        const pipelineId = result.pipeline.data.id;
        pipelineIds.push(pipelineId);

        console.log(`  Pipeline created successfully: ${pipelineId}`);

        // Start the pipeline immediately
        console.log(`  Starting pipeline ${pipelineId}...`);
        await vectorizeClient.startPipeline(pipelineId);
        console.log(`  Pipeline ${pipelineId} started successfully`);

      } catch (error) {
        console.log(`  Pipeline creation skipped for ${source.name}:`, error instanceof Error ? error.message : error);
      }
    }

    // Store pipeline IDs in the database
    if (pipelineIds.length > 0) {
      try {
        await query(
          `UPDATE tracking_sessions
           SET vectorize_pipeline_ids = $1, updated_at = NOW()
           WHERE id = $2`,
          [pipelineIds, this.sessionId]
        );
        console.log(`Stored ${pipelineIds.length} pipeline IDs in database`);
      } catch (error) {
        console.log('Pipeline ID storage skipped:', error instanceof Error ? error.message : error);
      }
    }

    console.log(`--- Pipeline Creation Complete ---\n`);
  }

  async processCandidate(
    candidate: string,
    topic: string,
    timeRange?: { start: Date; end: Date }
  ): Promise<StancePoint[]> {
    console.log(`\n********************************************`);
    console.log(`Processing Candidate: ${candidate}`);
    console.log(`Topic: ${topic}`);
    console.log(`********************************************\n`);

    // Step 1: Retrieve documents from Vectorize pipelines and store in Memora
    console.log(`Step 1: Retrieving and indexing content...`);
    const searchQuery = this.buildSearchQuery(candidate, topic);
    const scrapedRefs = await this.scraperAgent.scrapeAndIndex(
      candidate,
      topic,
      searchQuery
    );
    console.log(`  Retrieved ${scrapedRefs.length} references from pipelines\n`);

    // Step 2: Retrieve relevant references via RAG system (Hindsight + supplemental pipeline data)
    console.log(`Step 2: RAG retrieval for stance analysis...`);
    const relevantRefs = await this.ragSystem.retrieveRelevantReferences(
      candidate,
      topic,
      { timeRange, topK: 15 }
    );
    console.log(`  Retrieved ${relevantRefs.length} relevant references\n`);

    // Combine scraped and retrieved references
    const allRefs = this.deduplicateReferences([...scrapedRefs, ...relevantRefs]);

    if (allRefs.length === 0) {
      console.log(`No references found for ${candidate} on ${topic}`);
      console.log(`********************************************\n`);
      return [];
    }

    console.log(`Total unique references: ${allRefs.length}\n`);

    // Step 3: Extract stance from references
    console.log(`Step 3: Extracting stance from references...`);
    const extractedStance = await this.stanceExtractor.extractStance(
      candidate,
      topic,
      allRefs
    );
    console.log(`  Stance: ${extractedStance.stance}`);
    console.log(`  Confidence: ${extractedStance.confidence.toFixed(2)}`);
    console.log(`  Summary: ${extractedStance.stance_summary}`);
    if (extractedStance.reasoning) {
      console.log(`  Reasoning: ${extractedStance.reasoning.substring(0, 100)}...`);
    }
    console.log();

    // Step 4: Get previous stance to detect changes
    console.log(`Step 4: Checking for stance changes...`);
    const previousStance = await this.getPreviousStance(candidate, topic);
    let changeInfo = null;

    if (previousStance) {
      console.log(`  Previous stance found: ${previousStance.stance}`);
      const change = await this.stanceExtractor.detectStanceChange(
        previousStance.stance,
        extractedStance.stance,
        candidate,
        topic
      );

      if (change.has_changed) {
        console.log(`  STANCE CHANGE DETECTED!`);
        console.log(`    Change: ${change.change_description}`);
        console.log(`    Magnitude: ${change.change_magnitude}`);

        changeInfo = {
          previous_stance: previousStance.stance,
          change_description: change.change_description,
          change_magnitude: change.change_magnitude,
        };
      } else {
        console.log(`  No significant change detected`);
      }
    } else {
      console.log(`  No previous stance found (first analysis)`);
    }
    console.log();

    // Step 5: Store stance in Hindsight
    console.log(`Step 5: Storing stance in Hindsight...`);
    const opinionText = `${candidate}'s stance on ${topic}: ${extractedStance.stance_summary}`;

    try {
      await hindsightClient.retain(
        `scraper_${this.sessionId}`,
        opinionText,
        {
          context: 'opinion',
          timestamp: new Date(),
          metadata: { document_id: `stance_${Date.now()}` },
        }
      );
      console.log(`  Stored stance in Hindsight\n`);
    } catch (error) {
      console.log(`  Hindsight storage skipped:`, error instanceof Error ? error.message : error);
    }

    // Step 6: Save to database
    console.log(`Step 6: Saving stance point to database...`);
    const stancePoint = await this.saveStancePoint(
      candidate,
      topic,
      extractedStance,
      allRefs,
      changeInfo
    );
    console.log(`  Saved with ID: ${stancePoint.id}\n`);

    console.log(`********************************************`);
    console.log(`Candidate Processing Complete`);
    console.log(`********************************************\n`);

    return [stancePoint];
  }

  async processAllCandidates(
    candidates: string[],
    topic: string,
    location: Location,
    timeRange?: { start: Date; end: Date }
  ): Promise<StancePoint[]> {
    console.log(`\n========================================`);
    console.log(`Processing ${candidates.length} Candidates`);
    console.log(`========================================\n`);

    const allStances: StancePoint[] = [];

    for (const candidate of candidates) {
      try {
        // Initialize agent for this candidate
        await this.initialize(candidate, topic, location);

        // Process candidate
        const stances = await this.processCandidate(candidate, topic, timeRange);
        allStances.push(...stances);

        // Record activity in agent memory
        await this.scraperAgent.recordScrapingActivity(
          `Processed stance for ${candidate} on ${topic}`
        );
      } catch (error) {
        console.error(`Error processing candidate ${candidate}:`, error);
        // Continue with other candidates
      }
    }

    console.log(`\n========================================`);
    console.log(`All Candidates Processed`);
    console.log(`Total Stance Points: ${allStances.length}`);
    console.log(`========================================\n`);

    return allStances;
  }

  async getHistoricalStances(
    candidate: string,
    topic: string,
    startDate: Date,
    endDate: Date
  ): Promise<StancePoint[]> {
    console.log(`\n--- Retrieving Historical Stances ---`);
    console.log(`Candidate: ${candidate}, Topic: ${topic}`);
    console.log(`Date range: ${startDate.toLocaleDateString()} to ${endDate.toLocaleDateString()}`);

    // Query Hindsight for historical opinions (PRIMARY)
    let memoraResults;
    try {
      memoraResults = await hindsightClient.searchOpinions(
        `scraper_${this.sessionId}`,
        `${candidate} ${topic}`,
        { thinkingBudget: 100, topK: 50 }
      );
      console.log(`Found ${memoraResults.results?.length || 0} opinion memories from Memora`);
    } catch (error) {
      console.log(`Hindsight opinion search skipped:`, error instanceof Error ? error.message : error);
    }

    // Query database for historical stance points
    const dbResults = await query<any>(
      `SELECT * FROM stance_points
       WHERE session_id = $1
       AND candidate = $2
       AND topic = $3
       AND timestamp BETWEEN $4 AND $5
       ORDER BY timestamp ASC`,
      [this.sessionId, candidate, topic, startDate, endDate]
    );

    console.log(`Found ${dbResults.length} stance points from database`);

    const stances = await this.hydrateStancePoints(dbResults);

    console.log(`--- Historical Stances Retrieved ---\n`);

    return stances;
  }

  private async saveStancePoint(
    candidate: string,
    topic: string,
    extractedStance: any,
    references: Reference[],
    changeInfo: any
  ): Promise<StancePoint> {
    // Insert stance point
    const stanceResult = await queryOne<any>(
      `INSERT INTO stance_points
       (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       RETURNING *`,
      [
        this.sessionId,
        candidate,
        topic,
        extractedStance.stance,
        extractedStance.stance_summary,
        extractedStance.confidence,
        new Date(),
      ]
    );

    // Insert references
    for (const ref of references) {
      // Upsert reference
      const refResult = await queryOne<any>(
        `INSERT INTO "references" (url, title, excerpt, published_date, source_type, vectorize_id)
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT (url) DO UPDATE SET
           title = EXCLUDED.title,
           excerpt = EXCLUDED.excerpt
         RETURNING id`,
        [
          ref.url,
          ref.title,
          ref.excerpt,
          ref.published_date,
          ref.source_type,
          ref.vectorize_id,
        ]
      );

      // Link to stance point
      await query(
        `INSERT INTO stance_point_references (stance_point_id, reference_id)
         VALUES ($1, $2)
         ON CONFLICT DO NOTHING`,
        [stanceResult.id, refResult.id]
      );
    }

    return {
      ...stanceResult,
      sources: references,
      change_from_previous: changeInfo,
    };
  }

  private async getPreviousStance(
    candidate: string,
    topic: string
  ): Promise<StancePoint | null> {
    const result = await queryOne<any>(
      `SELECT * FROM stance_points
       WHERE session_id = $1
       AND candidate = $2
       AND topic = $3
       ORDER BY timestamp DESC
       LIMIT 1`,
      [this.sessionId, candidate, topic]
    );

    return result;
  }

  private async hydrateStancePoints(dbResults: any[]): Promise<StancePoint[]> {
    const stances: StancePoint[] = [];

    for (const row of dbResults) {
      // Get references for this stance point
      const refs = await query<any>(
        `SELECT r.* FROM references r
         JOIN stance_point_references spr ON r.id = spr.reference_id
         WHERE spr.stance_point_id = $1`,
        [row.id]
      );

      stances.push({
        ...row,
        sources: refs,
      });
    }

    return stances;
  }

  private buildSearchQuery(candidate: string, topic: string): string {
    return `"${candidate}" "${topic}" (stance OR position OR opinion OR policy OR statement)`;
  }

  private deduplicateReferences(refs: Reference[]): Reference[] {
    const seen = new Set<string>();
    return refs.filter((ref) => {
      if (seen.has(ref.url)) return false;
      seen.add(ref.url);
      return true;
    });
  }
}
