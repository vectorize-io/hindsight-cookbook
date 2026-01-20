/**
 * Hindsight Client Wrapper
 * Provides typed interface to Hindsight memory operations for blog content
 */
import { HindsightClient, type RecallResponse, type ReflectResponse, type RetainResponse } from '@vectorize-io/hindsight-client';
import 'dotenv/config';

const HINDSIGHT_URL = process.env.HINDSIGHT_API_URL || 'http://localhost:8888';
const BANK_ID = process.env.HINDSIGHT_BANK_ID || 'blog-memory';

// Initialize Hindsight client
export const hindsight = new HindsightClient({ baseUrl: HINDSIGHT_URL });

// Export bank ID for use in other modules
export const bankId = BANK_ID;

// Re-export types for convenience
export type { RecallResponse, ReflectResponse, RetainResponse };

/**
 * Blog post memory item for batch retain
 */
export interface BlogMemoryItem {
  content: string;
  context?: string;
  document_id?: string;
  timestamp?: string;
  tags?: string[];
}

/**
 * Retain (store) a single blog post in memory
 * Uses document_id for automatic upsert behavior - 
 * if the same document_id exists, old content is replaced
 */
export async function retainBlogPost(
  content: string,
  options: {
    documentId: string;
    context?: string;
    timestamp?: string;
  }
): Promise<RetainResponse> {
  return await hindsight.retain(BANK_ID, content, {
    documentId: options.documentId,
    context: options.context,
    timestamp: options.timestamp,
  });
}

/**
 * Retain multiple blog posts in batch
 * More efficient for syncing multiple posts at once
 */
export async function retainBlogPosts(
  items: BlogMemoryItem[],
  options?: {
    documentTags?: string[];
    async?: boolean;
  }
): Promise<RetainResponse> {
  return await hindsight.retainBatch(BANK_ID, items, {
    documentTags: options?.documentTags,
    async: options?.async,
  });
}

/**
 * Recall memories using semantic search
 * @param query - Natural language query (e.g., "posts about AI agents")
 * @param options - Recall options including budget, types, temporal filters
 */
export async function recallMemory(
  query: string,
  options?: {
    types?: string[];
    maxTokens?: number;
    budget?: 'low' | 'mid' | 'high';
    queryTimestamp?: string;  // For temporal queries like "posts from January 2025"
    includeEntities?: boolean;
  }
): Promise<RecallResponse> {
  return await hindsight.recall(BANK_ID, query, {
    types: options?.types,
    maxTokens: options?.maxTokens || 4096,
    budget: options?.budget || 'mid',
    queryTimestamp: options?.queryTimestamp,
    includeEntities: options?.includeEntities ?? true,
  });
}

/**
 * Reflect on memories to generate insights
 * Uses LLM to synthesize an answer based on stored blog content
 * @param query - Question to answer (e.g., "What are the main themes of my blog?")
 * @param options - Reflect options including budget
 */
export async function reflectOnMemory(
  query: string,
  options?: {
    context?: string;
    budget?: 'low' | 'mid' | 'high';
  }
): Promise<ReflectResponse> {
  return await hindsight.reflect(BANK_ID, query, {
    context: options?.context,
    budget: options?.budget || 'mid',
  });
}

/**
 * Set up the memory bank with appropriate configuration for blog content
 */
export async function setupBlogMemoryBank(
  name: string,
  background: string
): Promise<void> {
  await hindsight.createBank(BANK_ID, {
    name,
    background,
    disposition: {
      skepticism: 2,   // Trusting - blog content is authoritative
      literalism: 4,   // Literal - exact content matters for blog posts
      empathy: 3,      // Balanced
    },
  });
  console.log(`Memory bank "${BANK_ID}" configured successfully`);
}

/**
 * Get the memory bank profile
 */
export async function getBankProfile() {
  return await hindsight.getBankProfile(BANK_ID);
}

/**
 * List all memories with pagination
 */
export async function listMemories(options?: {
  limit?: number;
  offset?: number;
  type?: string;
  q?: string;
}) {
  return await hindsight.listMemories(BANK_ID, options);
}
