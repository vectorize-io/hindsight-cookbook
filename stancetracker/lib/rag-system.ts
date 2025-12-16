import { hindsightClient } from './hindsight-client';
import { Reference } from '@/types';

export class RAGSystem {
  private sessionId: string;
  private agentId: string;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
    this.agentId = `scraper_${sessionId}`;
  }

  async retrieveRelevantReferences(
    candidate: string,
    topic: string,
    options: {
      timeRange?: { start: Date; end: Date };
      topK?: number;
      minScore?: number;
    } = {}
  ): Promise<Reference[]> {
    const { timeRange, topK = 10, minScore = 0.5 } = options;

    console.log(`\n=== RAG System: Retrieving References ===`);
    console.log(`Candidate: ${candidate}, Topic: ${topic}`);
    console.log(`Top K: ${topK}, Min Score: ${minScore}`);

    // Use Hindsight's temporal-semantic memory system with temporal filtering
    const temporalQuery = timeRange
      ? `What did ${candidate} say about ${topic} between ${timeRange.start.toLocaleDateString()} and ${timeRange.end.toLocaleDateString()}?`
      : `${candidate}'s position on ${topic}`;

    let hindsightResults;
    try {
      console.log(`Querying Hindsight with temporal-semantic search...`);

      const recallOptions: any = {
        budget: 'high',
        maxTokens: 8192,
      };

      // Add temporal filtering if we have a time range
      if (timeRange) {
        // Use the end date as the query timestamp to retrieve memories up to that point
        recallOptions.queryTimestamp = timeRange.end.toISOString();
        console.log(`  Using query timestamp: ${timeRange.end.toISOString()}`);
      }

      hindsightResults = await hindsightClient.recall(
        this.agentId,
        temporalQuery,
        recallOptions
      );
      console.log(`  Hindsight returned ${hindsightResults.results?.length || 0} memory results`);
    } catch (error) {
      console.log(`  Hindsight recall skipped:`, error instanceof Error ? error.message : error);
      hindsightResults = { results: [] };
    }

    console.log(`Final result: ${hindsightResults.results?.length || 0} references`);
    console.log(`=== RAG System: Complete ===\n`);

    // For now, return empty array as we're not converting Hindsight results to references
    // In the future, we could convert Hindsight memories to Reference objects if needed
    return [];
  }

  async retrieveForTimePoint(
    candidate: string,
    topic: string,
    targetDate: Date,
    windowDays: number = 30
  ): Promise<Reference[]> {
    console.log(`\n--- Retrieving for time point: ${targetDate.toLocaleDateString()} (window: ${windowDays} days) ---`);

    // Retrieve references within a time window around the target date
    const start = new Date(targetDate);
    start.setDate(start.getDate() - windowDays);

    const end = new Date(targetDate);
    end.setDate(end.getDate() + windowDays);

    return this.retrieveRelevantReferences(candidate, topic, {
      timeRange: { start, end },
      topK: 15,
    });
  }

  async storeReference(reference: Reference, content: string): Promise<void> {
    console.log(`Storing reference in Hindsight: ${reference.title}`);

    // Store in Hindsight for semantic-temporal search
    try {
      await hindsightClient.retain(
        this.agentId,
        `Source: "${reference.title}" (${reference.source_type}). Content: ${content.substring(0, 500)}...`,
        {
          context: 'reference_storage',
          timestamp: reference.published_date,
          metadata: { document_id: `ref_${reference.id}` },
        }
      );
      console.log(`  Stored in Hindsight successfully`);
    } catch (error) {
      console.log(`  Hindsight storage skipped:`, error instanceof Error ? error.message : error);
    }
  }
}
