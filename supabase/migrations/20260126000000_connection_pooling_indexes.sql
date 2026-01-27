-- Connection Pooling and Query Optimization Migration
-- =====================================================
-- This migration adds indexes optimized for:
-- 1. Daily refresh pipeline batch operations
-- 2. today_games and upcoming_games view performance
-- 3. AI analysis and prediction market queries
-- 4. Connection pooling workload patterns
--
-- Analysis based on:
-- - supabase_client.py query patterns with timing decorator
-- - daily_refresh.py batch processing operations
-- - View definitions with multiple LATERAL joins
-- - EXISTS subqueries for prediction market flags

-- ============================================
-- SECTION 1: View Performance Indexes
-- ============================================
-- The today_games and upcoming_games views use multiple LATERAL subqueries
-- that can benefit from covering indexes.

-- Index for today's games filtering (most frequent query)
-- Covers: WHERE g.date = CURRENT_DATE
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_games_date_covering
ON games(date)
INCLUDE (id, home_team_id, away_team_id, season, tip_time, is_conference_game, home_score, away_score, status);

-- Composite index for date range queries (upcoming_games view)
-- Covers: WHERE g.date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_games_date_range
ON games(date, tip_time)
WHERE date >= '2024-01-01';  -- Partial index for recent data only

-- ============================================
-- SECTION 2: LATERAL Subquery Optimization
-- ============================================
-- Each LATERAL subquery in the views needs efficient index access

-- Spreads LATERAL: ORDER BY captured_at DESC LIMIT 1 for game_id
-- Already have idx_spreads_game_captured, but add covering index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spreads_game_covering
ON spreads(game_id, captured_at DESC)
INCLUDE (home_spread, home_ml, away_ml, over_under, home_spread_odds, away_spread_odds);

-- Rankings LATERAL: WHERE team_id = X AND season = Y ORDER BY week DESC LIMIT 1
-- Add covering index for the rank column
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rankings_team_season_covering
ON rankings(team_id, season, week DESC)
INCLUDE (rank);

-- Predictions LATERAL: WHERE game_id = X ORDER BY created_at DESC LIMIT 1
-- Add covering index for all selected columns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_predictions_game_covering
ON predictions(game_id, created_at DESC)
INCLUDE (predicted_home_cover_prob, confidence_tier, recommended_bet, edge_pct);

-- AI Analysis LATERAL: WHERE game_id = X AND ai_provider = Y ORDER BY created_at DESC LIMIT 1
-- Separate indexes for claude and grok queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_analysis_claude
ON ai_analysis(game_id, created_at DESC)
WHERE ai_provider = 'claude';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_analysis_grok
ON ai_analysis(game_id, created_at DESC)
WHERE ai_provider = 'grok';

-- Covering index for AI analysis with selected columns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_analysis_game_provider_covering
ON ai_analysis(game_id, ai_provider, created_at DESC)
INCLUDE (id, recommended_bet, confidence_score);

-- ============================================
-- SECTION 3: EXISTS Subquery Optimization
-- ============================================
-- Views use EXISTS subqueries for prediction market flags

-- Prediction markets EXISTS: WHERE pm.game_id = g.id AND pm.status = 'open'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pm_game_status
ON prediction_markets(game_id, status)
WHERE status = 'open';

-- Arbitrage opportunities EXISTS: WHERE ao.game_id = X AND ao.is_actionable = true AND ao.captured_at > NOW() - '24 hours'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_arb_game_actionable_recent
ON arbitrage_opportunities(game_id, is_actionable, captured_at DESC)
WHERE is_actionable = true;

-- ============================================
-- SECTION 4: Daily Refresh Batch Operations
-- ============================================
-- Optimize queries used during daily refresh pipeline

-- Games without scores (for update_game_results)
-- Pattern: WHERE date <= X AND home_score IS NULL LIMIT 50
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_games_needs_scoring
ON games(date DESC)
WHERE home_score IS NULL AND status != 'cancelled';

-- Games for predictions (upcoming, unplayed)
-- Pattern: WHERE date >= X AND home_score IS NULL
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_games_upcoming_unplayed
ON games(date, id)
WHERE home_score IS NULL;

-- Team lookup by normalized name (very frequent during odds processing)
-- Pattern: WHERE normalized_name = X or ILIKE '%X%'
-- Already have idx_teams_normalized, but ensure it's optimized
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_teams_normalized_lower
ON teams(LOWER(normalized_name));

-- Games by team matchup and date (odds processing)
-- Pattern: WHERE home_team_id = X AND away_team_id = Y AND date = Z
-- Already have idx_games_teams_date, verify it exists
DROP INDEX IF EXISTS idx_games_teams_date;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_games_matchup_date
ON games(home_team_id, away_team_id, date);

-- ============================================
-- SECTION 5: Batch Insert Optimization
-- ============================================
-- For batch inserts during daily refresh, we want to minimize
-- index maintenance overhead. These indexes help with UPSERT operations.

-- Spreads source uniqueness check (for deduplication)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spreads_game_source_captured
ON spreads(game_id, source, captured_at DESC);

-- Predictions by model for refresh
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_predictions_game_model
ON predictions(game_id, model_name);

-- ============================================
-- SECTION 6: Connection Pooling Statistics View
-- ============================================
-- Create a view for monitoring query performance

CREATE OR REPLACE VIEW query_performance_stats AS
SELECT
    'games' as table_name,
    reltuples::bigint as estimated_rows,
    pg_size_pretty(pg_total_relation_size('games')) as total_size,
    pg_size_pretty(pg_indexes_size('games')) as index_size
FROM pg_class WHERE relname = 'games'
UNION ALL
SELECT
    'spreads' as table_name,
    reltuples::bigint as estimated_rows,
    pg_size_pretty(pg_total_relation_size('spreads')) as total_size,
    pg_size_pretty(pg_indexes_size('spreads')) as index_size
FROM pg_class WHERE relname = 'spreads'
UNION ALL
SELECT
    'predictions' as table_name,
    reltuples::bigint as estimated_rows,
    pg_size_pretty(pg_total_relation_size('predictions')) as total_size,
    pg_size_pretty(pg_indexes_size('predictions')) as index_size
FROM pg_class WHERE relname = 'predictions'
UNION ALL
SELECT
    'ai_analysis' as table_name,
    reltuples::bigint as estimated_rows,
    pg_size_pretty(pg_total_relation_size('ai_analysis')) as total_size,
    pg_size_pretty(pg_indexes_size('ai_analysis')) as index_size
FROM pg_class WHERE relname = 'ai_analysis'
UNION ALL
SELECT
    'teams' as table_name,
    reltuples::bigint as estimated_rows,
    pg_size_pretty(pg_total_relation_size('teams')) as total_size,
    pg_size_pretty(pg_indexes_size('teams')) as index_size
FROM pg_class WHERE relname = 'teams'
UNION ALL
SELECT
    'rankings' as table_name,
    reltuples::bigint as estimated_rows,
    pg_size_pretty(pg_total_relation_size('rankings')) as total_size,
    pg_size_pretty(pg_indexes_size('rankings')) as index_size
FROM pg_class WHERE relname = 'rankings'
UNION ALL
SELECT
    'kenpom_ratings' as table_name,
    reltuples::bigint as estimated_rows,
    pg_size_pretty(pg_total_relation_size('kenpom_ratings')) as total_size,
    pg_size_pretty(pg_indexes_size('kenpom_ratings')) as index_size
FROM pg_class WHERE relname = 'kenpom_ratings'
UNION ALL
SELECT
    'haslametrics_ratings' as table_name,
    reltuples::bigint as estimated_rows,
    pg_size_pretty(pg_total_relation_size('haslametrics_ratings')) as total_size,
    pg_size_pretty(pg_indexes_size('haslametrics_ratings')) as index_size
FROM pg_class WHERE relname = 'haslametrics_ratings';

GRANT SELECT ON query_performance_stats TO authenticated;
GRANT SELECT ON query_performance_stats TO anon;

COMMENT ON VIEW query_performance_stats IS 'Table size and index statistics for performance monitoring';

-- ============================================
-- SECTION 7: Analyze Tables
-- ============================================
-- Update statistics after adding indexes

ANALYZE games;
ANALYZE spreads;
ANALYZE predictions;
ANALYZE ai_analysis;
ANALYZE teams;
ANALYZE rankings;
ANALYZE kenpom_ratings;
ANALYZE haslametrics_ratings;
ANALYZE prediction_markets;
ANALYZE arbitrage_opportunities;

-- ============================================
-- INDEX COMMENTS
-- ============================================

COMMENT ON INDEX idx_games_date_covering IS 'Covering index for today_games view - includes all frequently accessed columns';
COMMENT ON INDEX idx_games_date_range IS 'Partial index for upcoming_games view date range queries';
COMMENT ON INDEX idx_spreads_game_covering IS 'Covering index for spreads LATERAL subquery in views';
COMMENT ON INDEX idx_rankings_team_season_covering IS 'Covering index for rankings LATERAL subquery with rank column';
COMMENT ON INDEX idx_predictions_game_covering IS 'Covering index for predictions LATERAL subquery';
COMMENT ON INDEX idx_ai_analysis_claude IS 'Partial index for Claude AI analysis queries';
COMMENT ON INDEX idx_ai_analysis_grok IS 'Partial index for Grok AI analysis queries';
COMMENT ON INDEX idx_ai_analysis_game_provider_covering IS 'Covering index for AI analysis with provider-specific filtering';
COMMENT ON INDEX idx_pm_game_status IS 'Partial index for open prediction markets EXISTS check';
COMMENT ON INDEX idx_arb_game_actionable_recent IS 'Partial index for actionable arbitrage EXISTS check';
COMMENT ON INDEX idx_games_needs_scoring IS 'Partial index for games needing score updates';
COMMENT ON INDEX idx_games_upcoming_unplayed IS 'Index for predictions pipeline - upcoming unplayed games';
COMMENT ON INDEX idx_teams_normalized_lower IS 'Case-insensitive team name lookup index';
COMMENT ON INDEX idx_games_matchup_date IS 'Composite index for finding games by team matchup and date';
COMMENT ON INDEX idx_spreads_game_source_captured IS 'Index for spread deduplication during refresh';
COMMENT ON INDEX idx_predictions_game_model IS 'Index for prediction management by model name';
