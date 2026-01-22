/**
 * Query Examples for Blog Memory
 * 
 * Demonstrates various ways to query blog content using Hindsight:
 * - Semantic search (related content discovery)
 * - Temporal queries (posts from specific time periods)
 * - Topic-based queries
 * - Reflect for insights
 * 
 * Usage: npm run query
 */
import { recallMemory, reflectOnMemory, listMemories } from './hindsight-client.js';

// Helper to display results nicely
function displayResults(title: string, results: any): void {
  console.log('\n' + '='.repeat(60));
  console.log(`  ${title}`);
  console.log('='.repeat(60));
  
  if (typeof results === 'string') {
    console.log('\n' + results);
  } else if (Array.isArray(results)) {
    results.forEach((item, index) => {
      console.log(`\n[${index + 1}] ${item.text?.substring(0, 200) || JSON.stringify(item).substring(0, 200)}...`);
    });
  } else {
    console.log('\n' + JSON.stringify(results, null, 2));
  }
}

/**
 * Example 1: Semantic Search
 * Find content related to a topic
 */
async function semanticSearchExample(): Promise<void> {
  const query = 'AI agents and automation';
  
  console.log(`\nQuery: "${query}"`);
  
  const result = await recallMemory(query, {
    budget: 'mid',
    maxTokens: 2048,
    includeEntities: true,
  });
  
  displayResults('Semantic Search: AI Agents', result.results);
  console.log(`\nFound ${result.results.length} relevant memories`);
}

/**
 * Example 2: Temporal Query
 * Find posts from a specific time period
 */
async function temporalQueryExample(): Promise<void> {
  // Query for recent content with a temporal hint in the query
  const query = 'What did I write about in January 2025?';
  
  console.log(`\nQuery: "${query}"`);
  
  // Use queryTimestamp to set temporal context
  const result = await recallMemory(query, {
    budget: 'mid',
    maxTokens: 2048,
    // queryTimestamp helps Hindsight understand the temporal context
    queryTimestamp: '2025-01-31T23:59:59Z',
  });
  
  displayResults('Temporal Query: January 2025 Posts', result.results);
  console.log(`\nFound ${result.results.length} memories from this period`);
}

/**
 * Example 3: Topic-based Discovery
 * Find all posts about a specific technology
 */
async function topicDiscoveryExample(): Promise<void> {
  const query = 'Qwik framework and web development';
  
  console.log(`\nQuery: "${query}"`);
  
  const result = await recallMemory(query, {
    budget: 'high',  // Use high budget for comprehensive results
    maxTokens: 4096,
    includeEntities: true,
  });
  
  displayResults('Topic Discovery: Qwik Framework', result.results);
  console.log(`\nFound ${result.results.length} relevant posts`);
}

/**
 * Example 4: Reflect - Generate Insights
 * Use LLM to analyze and synthesize blog content
 */
async function reflectInsightsExample(): Promise<void> {
  const query = 'What are the main themes and topics I write about on my blog? Summarize my content focus.';
  
  console.log(`\nQuery: "${query}"`);
  
  const result = await reflectOnMemory(query, {
    budget: 'high',
  });
  
  displayResults('Reflect: Blog Theme Analysis', result.text);
}

/**
 * Example 5: Reflect - Content Recommendations
 * Generate ideas based on existing content
 */
async function reflectRecommendationsExample(): Promise<void> {
  const query = 'Based on my existing blog posts, what topics should I write about next? What gaps exist in my content?';
  
  console.log(`\nQuery: "${query}"`);
  
  const result = await reflectOnMemory(query, {
    budget: 'high',
  });
  
  displayResults('Reflect: Content Recommendations', result.text);
}

/**
 * Example 6: Related Content Discovery
 * Find posts related to a specific post (useful for "Related Posts" feature)
 */
async function relatedContentExample(): Promise<void> {
  const postTitle = 'Why I Chose Qwik for My Personal Website';
  const query = `Find blog posts related to "${postTitle}". What other content on my blog covers similar topics?`;
  
  console.log(`\nQuery: "${query}"`);
  
  const result = await recallMemory(query, {
    budget: 'mid',
    maxTokens: 2048,
  });
  
  displayResults('Related Content Discovery', result.results);
  console.log(`\nFound ${result.results.length} related posts`);
}

/**
 * Example 7: List All Memories
 * Paginate through all stored memories
 */
async function listAllMemoriesExample(): Promise<void> {
  console.log('\nListing stored memories...');
  
  const result = await listMemories({
    limit: 5,
    offset: 0,
  });
  
  displayResults(`Memory Bank Contents (${result.total} total)`, result.items);
}

// Main function - runs all examples
async function runExamples(): Promise<void> {
  console.log('=======================================');
  console.log('  Hindsight Blog Memory Query Examples');
  console.log('=======================================');
  console.log('\nMake sure you have synced your blog posts first: npm run sync\n');
  
  try {
    // Semantic Search
    await semanticSearchExample();
    
    // Temporal Query
    await temporalQueryExample();
    
    // Topic Discovery
    await topicDiscoveryExample();
    
    // Reflect - Insights
    await reflectInsightsExample();
    
    // Reflect - Recommendations
    await reflectRecommendationsExample();
    
    // Related Content
    await relatedContentExample();
    
    // List Memories
    await listAllMemoriesExample();
    
    console.log('\n\n=======================================');
    console.log('  All Examples Complete!');
    console.log('=======================================\n');
  } catch (error) {
    console.error('\nError running examples:');
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

// Run examples
runExamples();
