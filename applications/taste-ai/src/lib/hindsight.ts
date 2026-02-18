import { createHindsightTools, type HindsightClient, type Budget, type FactType } from '@vectorize-io/hindsight-ai-sdk';
import { groq } from '@ai-sdk/groq';

const HINDSIGHT_URL = process.env.HINDSIGHT_URL || 'http://localhost:8888';
const GROQ_MODEL = process.env.GROQ_MODEL || 'llama-3.3-70b-versatile';

export const BANK_ID = 'taste-ai'; // Shared bank for all taste-ai users

// HTTP client that implements the HindsightClient interface for agent tools,
// plus extra methods for direct API calls (createMentalModel, directives).
class SimpleHindsightClient implements HindsightClient {
  constructor(private baseUrl: string) {}

  async retain(
    bankId: string,
    content: string,
    options?: {
      timestamp?: Date | string;
      context?: string;
      metadata?: Record<string, string>;
      documentId?: string;
      tags?: string[];
      async?: boolean;
    }
  ) {
    const payload = {
      items: [{
        content,
        timestamp: options?.timestamp,
        context: options?.context,
        metadata: options?.metadata,
        document_id: options?.documentId,
        tags: options?.tags,
      }],
      async: options?.async,
    };

    const response = await fetch(`${this.baseUrl}/v1/default/banks/${bankId}/memories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Retain failed: ${response.statusText}`);
    }

    return response.json();
  }

  async recall(
    bankId: string,
    query: string,
    options?: {
      types?: FactType[];
      maxTokens?: number;
      budget?: Budget;
      trace?: boolean;
      queryTimestamp?: string;
      includeEntities?: boolean;
      maxEntityTokens?: number;
      includeChunks?: boolean;
      maxChunkTokens?: number;
    }
  ) {
    const response = await fetch(`${this.baseUrl}/v1/default/banks/${bankId}/memories/recall`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        types: options?.types,
        max_tokens: options?.maxTokens,
        budget: options?.budget,
        trace: options?.trace,
        query_timestamp: options?.queryTimestamp,
        include_entities: options?.includeEntities,
        max_entity_tokens: options?.maxEntityTokens,
        include_chunks: options?.includeChunks,
        max_chunk_tokens: options?.maxChunkTokens,
      }),
    });

    if (!response.ok) {
      throw new Error(`Recall failed: ${response.statusText}`);
    }

    return response.json();
  }

  async reflect(
    bankId: string,
    query: string,
    options?: {
      context?: string;
      budget?: Budget;
      maxTokens?: number;
    }
  ) {
    const response = await fetch(`${this.baseUrl}/v1/default/banks/${bankId}/reflect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        context: options?.context,
        budget: options?.budget,
        max_tokens: options?.maxTokens,
      }),
    });

    if (!response.ok) {
      throw new Error(`Reflect failed: ${response.statusText}`);
    }

    return response.json();
  }

  async getMentalModel(bankId: string, mentalModelId: string) {
    const response = await fetch(`${this.baseUrl}/v1/default/banks/${bankId}/mental-models/${mentalModelId}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      if (response.status === 404) {
        return null;
      }
      throw new Error(`Get mental model failed: ${response.statusText}`);
    }

    return response.json();
  }

  async getDocument(bankId: string, documentId: string) {
    const response = await fetch(`${this.baseUrl}/v1/default/banks/${bankId}/documents/${documentId}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      if (response.status === 404) {
        return null;
      }
      throw new Error(`Get document failed: ${response.statusText}`);
    }

    return response.json();
  }

  // Direct API calls — not exposed as agent tools

  async createMentalModel(
    bankId: string,
    options?: {
      id?: string;
      name?: string;
      sourceQuery?: string;
      tags?: string[];
      maxTokens?: number;
      trigger?: { refresh_after_consolidation?: boolean };
    }
  ) {
    const response = await fetch(`${this.baseUrl}/v1/default/banks/${bankId}/mental-models`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: options?.id,
        name: options?.name,
        source_query: options?.sourceQuery,
        tags: options?.tags,
        max_tokens: options?.maxTokens,
        trigger: options?.trigger,
      }),
    });

    if (!response.ok) {
      throw new Error(`Create mental model failed: ${response.statusText}`);
    }

    return response.json();
  }

  async listDirectives(
    bankId: string,
    options?: {
      tags?: string[];
      tagsMatch?: 'any' | 'all' | 'exact';
      activeOnly?: boolean;
      limit?: number;
      offset?: number;
    }
  ) {
    const params = new URLSearchParams();
    if (options?.tags) {
      options.tags.forEach(tag => params.append('tags', tag));
    }
    if (options?.tagsMatch) {
      params.append('tags_match', options.tagsMatch);
    }
    if (options?.activeOnly !== undefined) {
      params.append('active_only', String(options.activeOnly));
    }
    if (options?.limit) {
      params.append('limit', String(options.limit));
    }
    if (options?.offset) {
      params.append('offset', String(options.offset));
    }

    const queryString = params.toString();
    const url = `${this.baseUrl}/v1/default/banks/${bankId}/directives${queryString ? `?${queryString}` : ''}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`List directives failed: ${response.statusText}`);
    }

    return response.json();
  }

  async createDirective(
    bankId: string,
    options: {
      name: string;
      content: string;
      tags?: string[];
    }
  ) {
    const response = await fetch(`${this.baseUrl}/v1/default/banks/${bankId}/directives`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: options.name,
        content: options.content,
        tags: options.tags ?? [],
      }),
    });

    if (!response.ok) {
      throw new Error(`Create directive failed: ${response.statusText}`);
    }

    return response.json();
  }
}

export const hindsightClient = new SimpleHindsightClient(HINDSIGHT_URL);

export const llmModel = groq(GROQ_MODEL);

export const hindsightTools = createHindsightTools({
  client: hindsightClient,
  bankId: BANK_ID,
});

console.log(`[TasteAI] Connected to Hindsight at ${HINDSIGHT_URL}`);
console.log(`[TasteAI] Using LLM model: ${GROQ_MODEL}`);

// Helper to normalize username for document/tag IDs
export function normalizeUsername(username?: string): string {
  if (!username) return 'guest';
  return username.toLowerCase().replace(/[^a-z0-9]/g, '-');
}

// Get document ID for a specific user
export function getDocumentId(username?: string): string {
  return `app-state-${normalizeUsername(username)}`;
}

// Get mental model ID for a specific user and type
export function getMentalModelId(username: string, type: string = 'health'): string {
  return `${normalizeUsername(username)}-${type}`;
}

// Ensure language directive exists for user.
// Directives with matching tags are automatically applied to mental models during refresh.
export async function ensureLanguageDirective(username: string, language: string): Promise<void> {
  const userTag = `user:${username}`;
  const directiveTag = 'directive:language';

  try {
    const existing = await hindsightClient.listDirectives(BANK_ID, {
      tags: [userTag, directiveTag],
      tagsMatch: 'all',
      activeOnly: true,
      limit: 1,
    });

    if (existing.directives && existing.directives.length > 0) {
      console.log(`[TasteAI] Language directive already exists for ${username}`);
      return;
    }
  } catch (e) {
    console.log('[TasteAI] No existing language directive found, creating one');
  }

  try {
    await hindsightClient.createDirective(BANK_ID, {
      name: `${username}'s Language Preference`,
      content: `Always respond in ${language}. All meal suggestions, recommendations, and responses must be in ${language}.`,
      tags: [userTag, directiveTag],
    });

    console.log(`[TasteAI] Created language directive for ${username}: ${language}`);
  } catch (e) {
    console.error('[TasteAI] Failed to create language directive:', e);
  }
}

export interface StoredMeal {
  id: string;
  name: string;
  emoji: string;
  description?: string;
  type: string;
  date: string;
  timestamp: string;
  healthScore?: number;
  timeMinutes?: number;
  ingredients?: string[];
  instructions?: string;
  tags?: string[];
  action: 'ate' | 'cooked';
}

export interface HealthAssessment {
  score: number;
  trend: 'up' | 'down' | 'stable';
  insight: string;
  assessedAt: string;
  mealsCountAtAssessment: number;
}

export interface UserPreferences {
  nickname?: string;
  language?: string;
  cuisines?: string[];
  dietary?: string[];
  goals?: string[];
  dislikes?: string[];
}

export interface AppDocument {
  username: string;
  meals: StoredMeal[];
  preferences: UserPreferences;
  updatedAt: string;
}

export async function getAppDocument(username: string): Promise<AppDocument> {
  const docId = getDocumentId(username);

  try {
    const response = await hindsightClient.getDocument(BANK_ID, docId);

    if (response?.original_text) {
      const doc = JSON.parse(response.original_text) as AppDocument;

      // Fix nested structure from old data (unwrap if needed)
      if ((doc.preferences as any)?.preferences) {
        doc.preferences = (doc.preferences as any).preferences as UserPreferences;
      }

      return doc;
    }
  } catch (e) {
    console.log(`[TasteAI] No app document yet for ${username}, returning empty`);
  }

  return {
    username,
    meals: [],
    preferences: { nickname: username },
    updatedAt: new Date().toISOString()
  };
}

export async function saveAppDocument(doc: AppDocument): Promise<void> {
  const docId = getDocumentId(doc.username);
  const jsonContent = JSON.stringify(doc);
  const userTag = `user:${doc.username}`;

  console.log(`[TasteAI] Saving app document for ${doc.username} with tag: ${userTag}`);

  // Call the client directly so we can attach per-user tags.
  // Tags are user-specific per call, so they can't be set at tool-creation time.
  await hindsightClient.retain(BANK_ID, jsonContent, {
    documentId: docId,
    tags: [userTag],
  });

  console.log(`[TasteAI] Saved app document for ${doc.username} (${doc.meals.length} meals)`);
}

// Backwards compat aliases
export const getMealsDocument = getAppDocument;
export const saveMealsDocument = saveAppDocument;

export async function addMealToDocument(username: string, meal: Omit<StoredMeal, 'id' | 'timestamp'>): Promise<StoredMeal> {
  const doc = await getAppDocument(username);

  const newMeal: StoredMeal = {
    ...meal,
    id: `meal-${Date.now()}`,
    timestamp: new Date().toISOString(),
  };

  doc.meals.unshift(newMeal);
  doc.meals = doc.meals.slice(0, 50); // Keep last 50
  doc.updatedAt = new Date().toISOString();

  await saveAppDocument(doc);

  return newMeal;
}

export async function updatePreferences(username: string, prefs: Partial<UserPreferences>): Promise<void> {
  const doc = await getAppDocument(username);

  // Fix nested structure from old data (unwrap if needed)
  const currentPrefs = (doc.preferences as any)?.preferences || doc.preferences || {};
  doc.preferences = { ...currentPrefs, ...prefs };
  doc.updatedAt = new Date().toISOString();

  await saveAppDocument(doc);
  console.log(`[TasteAI] Updated preferences for ${username}:`, prefs);
}
