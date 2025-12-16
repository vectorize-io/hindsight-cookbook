-- Stance Tracker Database Schema

CREATE TABLE IF NOT EXISTS tracking_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    country VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    city VARCHAR(100),
    topic TEXT NOT NULL,
    candidates TEXT[] NOT NULL,
    timespan_start TIMESTAMP NOT NULL,
    timespan_end TIMESTAMP NOT NULL,
    frequency VARCHAR(20) NOT NULL CHECK (frequency IN ('hourly', 'daily', 'weekly')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
    scraping_mode VARCHAR(50) NOT NULL DEFAULT 'direct_web' CHECK (scraping_mode IN ('direct_web', 'vectorize_pipelines')),
    vectorize_pipeline_ids TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stance_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES tracking_sessions(id) ON DELETE CASCADE,
    candidate VARCHAR(200) NOT NULL,
    topic TEXT NOT NULL,
    stance TEXT NOT NULL,
    stance_summary TEXT NOT NULL,
    confidence DECIMAL(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    timestamp TIMESTAMP NOT NULL,
    memora_opinion_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_candidate_timestamp UNIQUE (session_id, candidate, timestamp)
);

CREATE TABLE IF NOT EXISTS "references" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    excerpt TEXT,
    published_date TIMESTAMP,
    source_type VARCHAR(50) NOT NULL,
    vectorize_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stance_point_references (
    stance_point_id UUID NOT NULL REFERENCES stance_points(id) ON DELETE CASCADE,
    reference_id UUID NOT NULL REFERENCES "references"(id) ON DELETE CASCADE,
    PRIMARY KEY (stance_point_id, reference_id)
);

CREATE TABLE IF NOT EXISTS scraper_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(255) NOT NULL UNIQUE,
    session_id UUID NOT NULL REFERENCES tracking_sessions(id) ON DELETE CASCADE,
    sources TEXT[] NOT NULL,
    search_query TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tracking_sessions_status ON tracking_sessions(status);
CREATE INDEX IF NOT EXISTS idx_stance_points_session ON stance_points(session_id);
CREATE INDEX IF NOT EXISTS idx_stance_points_candidate ON stance_points(candidate);
CREATE INDEX IF NOT EXISTS idx_stance_points_timestamp ON stance_points(timestamp);
CREATE INDEX IF NOT EXISTS idx_references_url ON "references"(url);
CREATE INDEX IF NOT EXISTS idx_scraper_configs_session ON scraper_configs(session_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_tracking_sessions_updated_at BEFORE UPDATE ON tracking_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scraper_configs_updated_at BEFORE UPDATE ON scraper_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
