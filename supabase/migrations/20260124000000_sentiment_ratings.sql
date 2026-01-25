-- Sentiment Ratings Table for Social Media Sentiment Analysis
-- Stores aggregated sentiment from Twitter, Reddit, and News sources

-- ============================================
-- SENTIMENT RATINGS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS sentiment_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    game_id UUID REFERENCES games(id) ON DELETE CASCADE,
    season INTEGER NOT NULL,

    -- Core sentiment metrics
    sentiment_score DECIMAL(5,3),  -- 0.000 to 1.000 (0=bearish, 0.5=neutral, 1=bullish)
    positive_pct DECIMAL(5,2),     -- Percentage of positive mentions
    negative_pct DECIMAL(5,2),     -- Percentage of negative mentions
    neutral_pct DECIMAL(5,2),      -- Percentage of neutral mentions

    -- Volume and trending
    volume VARCHAR(10),            -- 'low', 'medium', 'high'
    trending BOOLEAN DEFAULT false,

    -- Qualitative insights
    key_narratives TEXT[],         -- Key talking points from social media
    betting_insights TEXT[],       -- Betting-related observations
    sample_tweets TEXT[],          -- Sample tweets for context

    -- Metadata
    confidence DECIMAL(4,3),       -- 0.000 to 1.000 (based on sources available)
    source VARCHAR(20) DEFAULT 'aggregated',  -- 'twitter', 'reddit', 'news', 'aggregated'

    -- Timestamps
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    captured_date DATE DEFAULT CURRENT_DATE,

    -- Unique constraint: one sentiment rating per team/game/date
    UNIQUE(team_id, game_id, captured_date)
);

-- Add comments for documentation
COMMENT ON TABLE sentiment_ratings IS 'Social media sentiment analysis for teams (Twitter, Reddit, News)';
COMMENT ON COLUMN sentiment_ratings.sentiment_score IS 'Aggregated sentiment: 0=very negative, 0.5=neutral, 1=very positive';
COMMENT ON COLUMN sentiment_ratings.volume IS 'Discussion volume: low, medium, high';
COMMENT ON COLUMN sentiment_ratings.key_narratives IS 'Key talking points extracted from social media';
COMMENT ON COLUMN sentiment_ratings.betting_insights IS 'Betting-related observations from public sentiment';
COMMENT ON COLUMN sentiment_ratings.confidence IS 'Confidence in sentiment rating based on data quality';

-- ============================================
-- INDEXES
-- ============================================

-- Index for team lookups
CREATE INDEX idx_sentiment_team ON sentiment_ratings(team_id, season);

-- Index for game lookups
CREATE INDEX idx_sentiment_game ON sentiment_ratings(game_id);

-- Index for date-based queries
CREATE INDEX idx_sentiment_date ON sentiment_ratings(captured_date);

-- Index for finding trending teams
CREATE INDEX idx_sentiment_trending ON sentiment_ratings(trending, captured_date) WHERE trending = true;

-- Index for high confidence ratings
CREATE INDEX idx_sentiment_confidence ON sentiment_ratings(confidence DESC) WHERE confidence >= 0.7;

-- ============================================
-- VIEW: Latest Team Sentiment
-- ============================================
CREATE OR REPLACE VIEW latest_sentiment_ratings AS
SELECT DISTINCT ON (sr.team_id, sr.game_id)
    sr.id,
    sr.team_id,
    t.name as team_name,
    sr.game_id,
    sr.season,
    sr.sentiment_score,
    CASE
        WHEN sr.sentiment_score >= 0.6 THEN 'Bullish'
        WHEN sr.sentiment_score <= 0.4 THEN 'Bearish'
        ELSE 'Neutral'
    END as sentiment_label,
    sr.positive_pct,
    sr.negative_pct,
    sr.neutral_pct,
    sr.volume,
    sr.trending,
    sr.key_narratives,
    sr.betting_insights,
    sr.sample_tweets,
    sr.confidence,
    sr.source,
    sr.captured_at,
    sr.captured_date
FROM sentiment_ratings sr
JOIN teams t ON sr.team_id = t.id
ORDER BY sr.team_id, sr.game_id, sr.captured_at DESC;

COMMENT ON VIEW latest_sentiment_ratings IS 'Most recent sentiment rating for each team/game combination';

-- ============================================
-- VIEW: Game Sentiment Summary
-- ============================================
CREATE OR REPLACE VIEW game_sentiment_summary AS
SELECT
    g.id as game_id,
    g.date,
    ht.name as home_team,
    at.name as away_team,
    hs.sentiment_score as home_sentiment_score,
    CASE
        WHEN hs.sentiment_score >= 0.6 THEN 'Bullish'
        WHEN hs.sentiment_score <= 0.4 THEN 'Bearish'
        ELSE 'Neutral'
    END as home_sentiment_label,
    hs.volume as home_volume,
    hs.trending as home_trending,
    aws.sentiment_score as away_sentiment_score,
    CASE
        WHEN aws.sentiment_score >= 0.6 THEN 'Bullish'
        WHEN aws.sentiment_score <= 0.4 THEN 'Bearish'
        ELSE 'Neutral'
    END as away_sentiment_label,
    aws.volume as away_volume,
    aws.trending as away_trending,
    -- Sentiment differential (positive = home team has better sentiment)
    COALESCE(hs.sentiment_score, 0.5) - COALESCE(aws.sentiment_score, 0.5) as sentiment_differential
FROM games g
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams at ON g.away_team_id = at.id
LEFT JOIN LATERAL (
    SELECT * FROM sentiment_ratings
    WHERE team_id = g.home_team_id AND game_id = g.id
    ORDER BY captured_at DESC
    LIMIT 1
) hs ON true
LEFT JOIN LATERAL (
    SELECT * FROM sentiment_ratings
    WHERE team_id = g.away_team_id AND game_id = g.id
    ORDER BY captured_at DESC
    LIMIT 1
) aws ON true
WHERE g.date >= CURRENT_DATE
ORDER BY g.date, g.tip_time;

COMMENT ON VIEW game_sentiment_summary IS 'Sentiment summary for upcoming games with both teams';
