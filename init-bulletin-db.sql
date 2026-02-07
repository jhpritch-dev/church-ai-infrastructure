-- Episcopal Bulletin Generator - Database Initialization
-- This script runs automatically when the PostgreSQL container starts fresh.

-- Create Paperless database if needed
SELECT 'CREATE DATABASE paperless'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'paperless')\gexec

-- Bulletin tables (Phase 1 - minimal schema)
CREATE TABLE IF NOT EXISTS bulletins (
    id SERIAL PRIMARY KEY,
    parish_name VARCHAR(255) NOT NULL,
    service_date DATE NOT NULL,
    service_time VARCHAR(50),
    service_type VARCHAR(100),
    liturgical_season VARCHAR(100),
    filename VARCHAR(500),
    file_path VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hymn_selections (
    id SERIAL PRIMARY KEY,
    bulletin_id INTEGER REFERENCES bulletins(id) ON DELETE CASCADE,
    position VARCHAR(50) NOT NULL,  -- opening, sequence, communion_1, communion_2, closing
    hymn_number VARCHAR(10),
    hymn_title VARCHAR(255),
    hymn_tune VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bulletins_date ON bulletins(service_date DESC);
CREATE INDEX IF NOT EXISTS idx_hymn_selections_bulletin ON hymn_selections(bulletin_id);
