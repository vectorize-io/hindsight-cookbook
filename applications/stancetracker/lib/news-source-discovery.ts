import { llmClient } from './llm-client';
import { Location } from '@/types';

export interface NewsSource {
  name: string;
  url: string;
  description: string;
  coverage_area: string;
  relevance_score: number;
}

export class NewsSourceDiscovery {
  /**
   * Use LLM to discover the most relevant news sources for a topic and location
   */
  async discoverNewsSources(
    topic: string,
    location: Location,
    maxSources: number = 3
  ): Promise<NewsSource[]> {
    const locationStr = [location.city, location.state, location.country]
      .filter(Boolean)
      .join(', ');

    const prompt = `You are a news source expert. Identify the ${maxSources} most authoritative and relevant news sources for tracking political coverage about "${topic}" in ${locationStr}.

Requirements:
- Focus on LOCAL news sources that cover ${locationStr} politics
- Include major regional newspapers, TV stations, or news websites
- Prioritize sources with strong political coverage and investigative journalism
- Provide actual, real news organization websites (not social media or aggregators)
- Return only sources that are likely to have coverage of local political issues

For each source, provide:
1. Name: Official name of the news organization
2. URL: Primary website URL (must be a real, working news site)
3. Description: Brief description of the news source
4. Coverage Area: Geographic area they primarily cover
5. Relevance Score: 1-10 score for relevance to this topic/location

Return as a JSON array of objects with these fields: name, url, description, coverage_area, relevance_score`;

    try {
      const response = await llmClient.complete(prompt, {
        temperature: 0.3,
        maxTokens: 1000,
      });

      // Parse the LLM response to extract news sources
      const sources = this.parseNewsSourcesFromResponse(response);

      // Sort by relevance score
      sources.sort((a, b) => b.relevance_score - a.relevance_score);

      return sources.slice(0, maxSources);
    } catch (error) {
      console.error('Error discovering news sources:', error);

      // Fallback to generic sources based on location
      return this.getFallbackSources(location, topic);
    }
  }

  /**
   * Parse LLM response to extract structured news source data
   */
  private parseNewsSourcesFromResponse(response: string): NewsSource[] {
    try {
      // Try to extract JSON from the response
      const jsonMatch = response.match(/\[[\s\S]*\]/);
      if (jsonMatch) {
        const sources = JSON.parse(jsonMatch[0]);
        return sources.map((s: any) => ({
          name: s.name || s.Name || '',
          url: s.url || s.URL || '',
          description: s.description || s.Description || '',
          coverage_area: s.coverage_area || s.Coverage_Area || s['Coverage Area'] || '',
          relevance_score: Number(s.relevance_score || s.Relevance_Score || s['Relevance Score'] || 5),
        }));
      }
    } catch (error) {
      console.error('Error parsing news sources from LLM response:', error);
    }

    // If parsing fails, try to extract sources manually
    return this.extractSourcesManually(response);
  }

  /**
   * Extract sources manually from unstructured text
   */
  private extractSourcesManually(response: string): NewsSource[] {
    const sources: NewsSource[] = [];
    const lines = response.split('\n');

    let currentSource: Partial<NewsSource> = {};

    for (const line of lines) {
      if (line.match(/name:/i)) {
        if (currentSource.name) {
          sources.push(currentSource as NewsSource);
          currentSource = {};
        }
        currentSource.name = line.replace(/.*name:\s*/i, '').trim();
      } else if (line.match(/url:/i)) {
        currentSource.url = line.replace(/.*url:\s*/i, '').trim();
      } else if (line.match(/description:/i)) {
        currentSource.description = line.replace(/.*description:\s*/i, '').trim();
      } else if (line.match(/coverage.?area:/i)) {
        currentSource.coverage_area = line.replace(/.*coverage.?area:\s*/i, '').trim();
      } else if (line.match(/relevance.?score:/i)) {
        const scoreMatch = line.match(/(\d+)/);
        currentSource.relevance_score = scoreMatch ? Number(scoreMatch[1]) : 5;
      }
    }

    if (currentSource.name) {
      sources.push(currentSource as NewsSource);
    }

    return sources;
  }

  /**
   * Fallback sources when LLM discovery fails
   */
  private getFallbackSources(location: Location, topic: string): NewsSource[] {
    const sources: NewsSource[] = [];

    // Add state/province level sources
    if (location.state) {
      // This is a simplified fallback - in production, you'd have a database of known sources
      sources.push({
        name: `${location.state} State News`,
        url: `https://www.google.com/search?q=${encodeURIComponent(location.state + ' news')}`,
        description: `General news coverage for ${location.state}`,
        coverage_area: location.state,
        relevance_score: 5,
      });
    }

    // Add city level sources
    if (location.city) {
      sources.push({
        name: `${location.city} Local News`,
        url: `https://www.google.com/search?q=${encodeURIComponent(location.city + ' news')}`,
        description: `Local news coverage for ${location.city}`,
        coverage_area: location.city,
        relevance_score: 7,
      });
    }

    return sources;
  }

  /**
   * Generate RSS feed URLs or sitemap URLs for a news source
   */
  async discoverContentFeeds(newsSource: NewsSource): Promise<string[]> {
    const feeds: string[] = [];

    // Common RSS feed patterns
    const commonFeedPaths = [
      '/rss',
      '/feed',
      '/rss.xml',
      '/feed.xml',
      '/feeds/news',
      '/rss/news',
      '/api/rss',
    ];

    const baseUrl = new URL(newsSource.url).origin;

    for (const path of commonFeedPaths) {
      feeds.push(`${baseUrl}${path}`);
    }

    // Add sitemap
    feeds.push(`${baseUrl}/sitemap.xml`);
    feeds.push(`${baseUrl}/sitemap_news.xml`);

    return feeds;
  }
}

export const newsSourceDiscovery = new NewsSourceDiscovery();
