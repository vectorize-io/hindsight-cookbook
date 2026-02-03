import { hindsightClient } from './hindsight-client';
import { webScraper } from './web-scraper';
import { queryOne } from './db';
import { Reference } from '@/types';

export interface ScraperSource {
  name: string;
  url: string;
  type: 'news' | 'social' | 'speech' | 'press_release' | 'interview';
}

export interface ScrapedContent {
  url: string;
  title: string;
  content: string;
  published_date: Date;
  source_type: string;
}

export class ScraperAgent {
  private agentId: string;
  private sessionId: string;

  constructor(sessionId: string) {
    this.agentId = `scraper_${sessionId}`;
    this.sessionId = sessionId;
  }

  async initialize(
    candidate: string,
    topic: string,
    location: { country: string; state?: string; city?: string }
  ): Promise<void> {
    console.log(`Initializing scraper bank for ${candidate} on ${topic}`);

    // Create Hindsight bank with background context
    await hindsightClient.createBank(
      this.agentId,
      {
        name: `Scraper: ${candidate} on ${topic}`,
        background: `I am a content retrieval system tracking ${candidate}'s stance on ${topic} in ${location.city || location.state || location.country}. I gather and organize information from multiple sources to build a comprehensive temporal-semantic memory of positions and statements.`,
      }
    );

    // Store initial memory about the tracking task
    await hindsightClient.retainBatch(
      this.agentId,
      [
        {
          content: `Tracking ${candidate}'s stance on ${topic}`,
          context: 'scraper_initialization',
          timestamp: new Date(),
        },
        {
          content: `Geographic focus: ${location.city || location.state || location.country}`,
          context: 'scraper_initialization',
          timestamp: new Date(),
        },
      ]
    );

    console.log(`Scraper bank ${this.agentId} initialized with Hindsight`);
  }

  async scrapeAndIndex(
    candidate: string,
    topic: string,
    searchQuery: string,
    sources?: ScraperSource[]
  ): Promise<Reference[]> {
    console.log(`\n=== Scraping Content for ${candidate} on ${topic} ===`);
    console.log(`Query: ${searchQuery}`);

    // Use direct web scraping only
    return await this.scrapeDirectWeb(candidate, topic);
  }

  private async scrapeDirectWeb(
    candidate: string,
    topic: string
  ): Promise<Reference[]> {
    console.log(`\n--- Direct Web Scraping ---`);

    // Get location and timespan from session
    const session = await queryOne(
      'SELECT country, state, city, timespan_start, timespan_end FROM tracking_sessions WHERE id = $1',
      [this.sessionId]
    );

    const location = session ? {
      country: session.country,
      state: session.state,
      city: session.city,
    } : undefined;

    const timeRange = session && session.timespan_start && session.timespan_end ? {
      start: new Date(session.timespan_start),
      end: new Date(session.timespan_end),
    } : undefined;

    // Search the web with timespan
    const searchResults = await webScraper.searchWeb(
      candidate,
      topic,
      location,
      10,
      timeRange
    );

    console.log(`Found ${searchResults.length} web results`);

    // Convert to references
    const references = webScraper.convertToReferences(searchResults);

    // Store in Hindsight for each result with the article's published date
    for (const result of searchResults) {
      if (result.content) {
        try {
          // Use the article's published date if available, otherwise use current date
          const eventDate = result.publishedDate ? new Date(result.publishedDate) : new Date();

          await hindsightClient.retain(
            this.agentId,
            `${result.title}: ${result.content.substring(0, 1000)}`,
            {
              context: 'web_search_result',
              timestamp: eventDate, // Store with article's actual date
              metadata: {
                url: result.url,
                published_date: result.publishedDate || new Date().toISOString(),
                document_id: `web_${Date.now()}_${Math.random()}`,
              }
            }
          );
        } catch (error) {
          console.log(`Hindsight storage skipped for ${result.url}:`, error instanceof Error ? error.message : error);
        }
      }
    }

    console.log(`Stored ${searchResults.length} results in Hindsight`);
    console.log(`--- Direct Web Scraping Complete ---\n`);

    return references;
  }


  async recordScrapingActivity(activity: string): Promise<void> {
    try {
      await hindsightClient.retain(
        this.agentId,
        activity,
        {
          context: 'agent_activity',
          timestamp: new Date(),
          metadata: { document_id: `activity_${Date.now()}` },
        }
      );
    } catch (error) {
      console.log('Activity recording skipped:', error instanceof Error ? error.message : error);
    }
  }

  async getAgentMemories(query: string): Promise<any> {
    try {
      return await hindsightClient.recall(this.agentId, query, {
        budget: 'mid',
        maxTokens: 4096,
      });
    } catch (error) {
      console.log('Memory recall skipped:', error instanceof Error ? error.message : error);
      return { results: [] };
    }
  }
}
