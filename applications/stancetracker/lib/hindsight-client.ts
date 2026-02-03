/**
 * Hindsight Client - Using official @vectorize-io/hindsight-client
 */

import { HindsightClient } from '@vectorize-io/hindsight-client';

const HINDSIGHT_API_URL = process.env.HINDSIGHT_API_URL || 'http://localhost:8888';

export const hindsightClient = new HindsightClient({ baseUrl: HINDSIGHT_API_URL });

// Re-export types from the official client for backwards compatibility
export type { HindsightClient };
