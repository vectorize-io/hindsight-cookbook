import { HindsightClient } from '@vectorize-io/hindsight-client';

const BASE_URL = process.env.HINDSIGHT_API_URL ?? 'http://localhost:8888';

export const hindsight = new HindsightClient({ baseUrl: BASE_URL });
