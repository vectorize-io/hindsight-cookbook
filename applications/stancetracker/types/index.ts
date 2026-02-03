export interface Location {
  country: string;
  state?: string;
  city?: string;
}

export interface TrackingSession {
  id: string;
  location: Location;
  topic: string;
  candidates: string[];
  timespan: {
    start: Date;
    end: Date;
  };
  frequency: 'hourly' | 'daily' | 'weekly';
  status: 'active' | 'paused' | 'completed';
  created_at: Date;
  updated_at: Date;
}

export interface Reference {
  id: string;
  url: string;
  title: string;
  excerpt: string;
  published_date: Date;
  source_type: 'news' | 'social' | 'speech' | 'press_release' | 'interview' | 'other';
  vectorize_id?: string;
}

export interface StancePoint {
  id: string;
  session_id: string;
  candidate: string;
  topic: string;
  stance: string;
  stance_summary: string;
  confidence: number;
  timestamp: Date;
  sources: Reference[];
  change_from_previous?: {
    previous_stance: string;
    change_description: string;
    change_magnitude: number;
  };
  hindsight_memory_id?: string;
}

export interface TimelineData {
  candidate: string;
  points: StancePoint[];
}

export type FrequencyType = 'hourly' | 'daily' | 'weekly';

export interface ScraperConfig {
  agent_id: string;
  session_id: string;
  sources: string[];
  search_query: string;
  enabled: boolean;
}

export interface HindsightBank {
  bank_id: string;
  name?: string;
  background?: string;
  disposition?: any;
}

export interface HindsightMemoryItem {
  content: string;
  context?: string;
  timestamp?: Date | string;
  metadata?: Record<string, string>;
  document_id?: string;
}

export interface HindsightRecallResult {
  content: string;
  timestamp?: string;
  context?: string;
  metadata?: Record<string, any>;
  score?: number;
}
