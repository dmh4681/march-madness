-- Haslametrics Team Ratings Table
-- Stores advanced analytics from Haslametrics (FREE alternative to KenPom)
-- Uses "All-Play Percentage" methodology instead of efficiency margin

CREATE TABLE IF NOT EXISTS haslametrics_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id),
    season INTEGER NOT NULL,

    -- Core Haslametrics Rankings
    rank INTEGER,                        -- Overall Haslametrics ranking

    -- Efficiency Metrics (points per 100 possessions)
    offensive_efficiency DECIMAL(6,2),   -- Offensive Efficiency
    defensive_efficiency DECIMAL(6,2),   -- Defensive Efficiency
    efficiency_margin DECIMAL(6,2),      -- OE - DE

    -- Shooting Efficiency
    ft_pct DECIMAL(6,3),                 -- Free Throw %
    fg_pct DECIMAL(6,3),                 -- Field Goal % (2-pointers)
    three_pct DECIMAL(6,3),              -- Three-Point %

    -- Pace & Tempo
    pace DECIMAL(6,2),                   -- Possessions per 40 minutes

    -- Momentum Indicators (unique to Haslametrics)
    momentum_overall DECIMAL(6,3),       -- Overall momentum
    momentum_offense DECIMAL(6,3),       -- Offensive momentum
    momentum_defense DECIMAL(6,3),       -- Defensive momentum

    -- Quality Metrics
    consistency DECIMAL(6,3),            -- Performance consistency
    sos DECIMAL(6,3),                    -- Strength of Schedule
    sos_rank INTEGER,
    record_quality DECIMAL(6,3),         -- Record quality indicator
    rpi DECIMAL(6,3),                    -- RPI rating

    -- All-Play Percentage (unique Haslametrics methodology)
    -- "If X played Y on neutral court, who wins?" across all D1 matchups
    all_play_pct DECIMAL(6,3),

    -- Recent Performance
    last_5_record TEXT,                  -- e.g., "4-1"

    -- Quadrant Records (NCAA tournament seeding context)
    quad_1_record TEXT,                  -- e.g., "3-2"
    quad_2_record TEXT,
    quad_3_record TEXT,
    quad_4_record TEXT,

    -- Record
    wins INTEGER,
    losses INTEGER,

    -- Conference
    conference TEXT,

    -- Metadata
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    captured_date DATE DEFAULT CURRENT_DATE,
    source TEXT DEFAULT 'haslametrics',

    -- Unique constraint: one rating per team per season per capture date
    UNIQUE(team_id, season, captured_date)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_hasla_team_season ON haslametrics_ratings(team_id, season);
CREATE INDEX IF NOT EXISTS idx_hasla_season_rank ON haslametrics_ratings(season, rank);
CREATE INDEX IF NOT EXISTS idx_hasla_captured ON haslametrics_ratings(captured_at);

-- Grant access
GRANT SELECT ON haslametrics_ratings TO authenticated;
GRANT SELECT ON haslametrics_ratings TO anon;

-- Create a view for latest Haslametrics ratings per team
CREATE OR REPLACE VIEW latest_haslametrics_ratings AS
SELECT DISTINCT ON (team_id, season)
    hr.*,
    t.name as team_name,
    t.normalized_name
FROM haslametrics_ratings hr
JOIN teams t ON hr.team_id = t.id
ORDER BY team_id, season, captured_at DESC;

GRANT SELECT ON latest_haslametrics_ratings TO authenticated;
GRANT SELECT ON latest_haslametrics_ratings TO anon;

-- Add comment
COMMENT ON TABLE haslametrics_ratings IS 'Haslametrics advanced analytics data - FREE, uses All-Play Percentage methodology';
