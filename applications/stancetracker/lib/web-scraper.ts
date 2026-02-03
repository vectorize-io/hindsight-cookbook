import { Reference } from '@/types';

export interface WebSearchResult {
  title: string;
  url: string;
  snippet: string;
  content?: string;
  publishedDate?: string;
}

export class WebScraper {
  private tavilyApiKey?: string;

  constructor() {
    this.tavilyApiKey = process.env.TAVILY_API_KEY;
  }

  /**
   * Search the web for articles about a candidate and topic
   */
  async searchWeb(
    candidate: string,
    topic: string,
    location?: { country: string; state?: string; city?: string },
    maxResults: number = 10,
    timeRange?: { start: Date; end: Date }
  ): Promise<WebSearchResult[]> {
    const locationStr = location?.city || location?.state || location?.country || '';
    const query = `${candidate} ${topic} ${locationStr} news article statement position`;

    console.log(`\n=== Web Search ===`);
    console.log(`Query: ${query}`);
    if (timeRange) {
      console.log(`Time range: ${timeRange.start.toISOString().split('T')[0]} to ${timeRange.end.toISOString().split('T')[0]}`);
    }

    // Use Tavily if available, otherwise fallback to basic search
    if (this.tavilyApiKey) {
      return await this.searchWithTavily(query, maxResults, timeRange);
    } else {
      console.log('Tavily API key not found, using fallback search');
      return await this.fallbackSearch(candidate, topic, locationStr, maxResults);
    }
  }

  /**
   * Search using Tavily API (best for research and news)
   */
  private async searchWithTavily(
    query: string,
    maxResults: number,
    timeRange?: { start: Date; end: Date }
  ): Promise<WebSearchResult[]> {
    try {
      console.log('Searching with Tavily API...');

      // Calculate days parameter for Tavily
      let days: number | undefined;
      if (timeRange) {
        const daysDiff = Math.ceil((timeRange.end.getTime() - timeRange.start.getTime()) / (1000 * 60 * 60 * 24));
        days = Math.max(1, daysDiff); // Tavily requires at least 1 day
        console.log(`Limiting search to articles from last ${days} days`);
      }

      const requestBody: any = {
        api_key: this.tavilyApiKey,
        query,
        search_depth: 'advanced',
        include_answer: false,
        include_raw_content: true,
        max_results: maxResults,
        include_domains: [],
        exclude_domains: [],
      };

      // Add days parameter if we have a time range
      if (days !== undefined) {
        requestBody.days = days;
      }

      const response = await fetch('https://api.tavily.com/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`Tavily API error: ${response.status}`);
      }

      const data = await response.json();

      const results: WebSearchResult[] = data.results.map((result: any) => ({
        title: result.title,
        url: result.url,
        snippet: result.content,
        content: result.raw_content || result.content,
        publishedDate: result.published_date,
      }));

      console.log(`Found ${results.length} results from Tavily`);

      // Additional client-side filtering if we have specific start/end dates
      if (timeRange && timeRange.start) {
        const filtered = results.filter(result => {
          if (!result.publishedDate) return true; // Keep if no date
          const pubDate = new Date(result.publishedDate);
          return pubDate >= timeRange.start && pubDate <= timeRange.end;
        });
        console.log(`Filtered to ${filtered.length} results within exact date range`);
        return filtered;
      }

      return results;
    } catch (error) {
      console.error('Tavily search error:', error);
      return [];
    }
  }

  /**
   * Fallback search using known news sources
   */
  private async fallbackSearch(
    candidate: string,
    topic: string,
    location: string,
    maxResults: number
  ): Promise<WebSearchResult[]> {
    console.log('Using fallback search strategy...');

    // Generate search URLs for known news sources
    const searchUrls = this.generateSearchUrls(candidate, topic, location);

    const results: WebSearchResult[] = [];

    for (const url of searchUrls.slice(0, maxResults)) {
      try {
        const content = await this.fetchAndParse(url);
        if (content) {
          results.push({
            title: `${candidate} on ${topic}`,
            url,
            snippet: content.substring(0, 300),
            content,
          });
        }
      } catch (error) {
        console.log(`Failed to fetch ${url}:`, error instanceof Error ? error.message : error);
      }
    }

    console.log(`Found ${results.length} results from fallback search`);
    return results;
  }

  /**
   * Generate URLs for common news sources
   */
  private generateSearchUrls(candidate: string, topic: string, location: string): string[] {
    const encodedCandidate = encodeURIComponent(candidate);
    const encodedTopic = encodeURIComponent(topic);
    const encodedLocation = encodeURIComponent(location);

    // For Canadian politicians, focus on Canadian news sources
    if (location.toLowerCase().includes('canada') || location.toLowerCase().includes('ottawa')) {
      return [
        `https://www.cbc.ca/search?q=${encodedCandidate}+${encodedTopic}`,
        `https://ottawacitizen.com/?s=${encodedCandidate}+${encodedTopic}`,
        `https://www.ctvnews.ca/search?q=${encodedCandidate}+${encodedTopic}`,
        `https://globalnews.ca/search/${encodedCandidate}+${encodedTopic}/`,
        `https://www.theglobeandmail.com/search/?q=${encodedCandidate}+${encodedTopic}`,
      ];
    }

    // General news sources
    return [
      `https://news.google.com/search?q=${encodedCandidate}+${encodedTopic}+${encodedLocation}`,
    ];
  }

  /**
   * Fetch and parse content from a URL
   */
  async fetchAndParse(url: string): Promise<string | null> {
    try {
      const response = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; StanceTracker/1.0)',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const html = await response.text();

      // Basic HTML parsing - extract text content
      // Remove scripts and styles
      let text = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
      text = text.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');

      // Remove HTML tags
      text = text.replace(/<[^>]+>/g, ' ');

      // Clean up whitespace
      text = text.replace(/\s+/g, ' ').trim();

      // Limit length
      return text.substring(0, 5000);
    } catch (error) {
      console.log(`Error fetching ${url}:`, error instanceof Error ? error.message : error);
      return null;
    }
  }

  /**
   * Convert search results to References
   */
  convertToReferences(results: WebSearchResult[]): Reference[] {
    return results.map((result, index) => ({
      id: `web-${Date.now()}-${index}`,
      url: result.url,
      title: result.title,
      excerpt: result.snippet,
      published_date: result.publishedDate ? new Date(result.publishedDate) : new Date(),
      source_type: 'news',
    }));
  }
}

export const webScraper = new WebScraper();
