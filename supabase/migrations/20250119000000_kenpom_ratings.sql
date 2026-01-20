-- KenPom Team Ratings Table
-- Stores advanced analytics from KenPom for enhanced AI analysis

CREATE TABLE IF NOT EXISTS kenpom_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id),
    season INTEGER NOT NULL,

    -- Core KenPom Rankings
    rank INTEGER,                    -- Overall KenPom ranking

    -- Adjusted Efficiency Metrics (points per 100 possessions)
    adj_efficiency_margin DECIMAL(6,2),  -- AdjEM = AdjO - AdjD
    adj_offense DECIMAL(6,2),            -- Adjusted Offensive Efficiency
    adj_offense_rank INTEGER,
    adj_defense DECIMAL(6,2),            -- Adjusted Defensive Efficiency
    adj_defense_rank INTEGER,

    -- Tempo & Possession
    adj_tempo DECIMAL(6,2),              -- Adjusted Tempo (possessions per 40 min)
    adj_tempo_rank INTEGER,

    -- Strength of Schedule
    sos_adj_em DECIMAL(6,2),             -- Strength of Schedule (AdjEM)
    sos_adj_em_rank INTEGER,
    sos_opp_offense DECIMAL(6,2),        -- Opponents' Adj Offense
    sos_opp_offense_rank INTEGER,
    sos_opp_defense DECIMAL(6,2),        -- Opponents' Adj Defense
    sos_opp_defense_rank INTEGER,

    -- Non-Conference SOS
    ncsos_adj_em DECIMAL(6,2),           -- Non-Conference SOS
    ncsos_adj_em_rank INTEGER,

    -- Luck Factor
    luck DECIMAL(6,3),                   -- Luck rating
    luck_rank INTEGER,

    -- Record
    wins INTEGER,
    losses INTEGER,

    -- Conference
    conference TEXT,

    -- Metadata
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    captured_date DATE DEFAULT CURRENT_DATE,
    source TEXT DEFAULT 'kenpom',

    -- Unique constraint: one rating per team per season per capture date
    UNIQUE(team_id, season, captured_date)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_kenpom_team_season ON kenpom_ratings(team_id, season);
CREATE INDEX IF NOT EXISTS idx_kenpom_season_rank ON kenpom_ratings(season, rank);
CREATE INDEX IF NOT EXISTS idx_kenpom_captured ON kenpom_ratings(captured_at);

-- Grant access
GRANT SELECT ON kenpom_ratings TO authenticated;
GRANT SELECT ON kenpom_ratings TO anon;

-- Create a view for latest KenPom ratings per team
CREATE OR REPLACE VIEW latest_kenpom_ratings AS
SELECT DISTINCT ON (team_id, season)
    kr.*,
    t.name as team_name,
    t.normalized_name
FROM kenpom_ratings kr
JOIN teams t ON kr.team_id = t.id
ORDER BY team_id, season, captured_at DESC;

GRANT SELECT ON latest_kenpom_ratings TO authenticated;
GRANT SELECT ON latest_kenpom_ratings TO anon;

-- Add comment
COMMENT ON TABLE kenpom_ratings IS 'KenPom advanced analytics data - requires KenPom subscription to populate';
