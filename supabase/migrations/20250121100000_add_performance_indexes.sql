-- Performance Indexes Migration
-- Adds strategic indexes to improve query performance for common access patterns
--
-- Analysis performed:
-- 1. Reviewed supabase_client.py query patterns
-- 2. Reviewed daily_refresh.py data pipeline queries
-- 3. Identified slow query patterns from views (today_games, latest_*_ratings)

-- ============================================
-- GAMES TABLE - Composite Indexes
-- ============================================

-- Composite index for date + status queries (most common pattern)
-- Used by: upcoming games, today's games, filtered game lists
-- Existing: idx_games_date, idx_games_status (separate)
-- This composite index covers both columns for better performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_games_date_status
ON games(date, status);

-- Composite index for finding games by team + date (used in odds processing)
-- Pattern: WHERE home_team_id = X AND away_team_id = Y AND date = Z
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_games_teams_date
ON games(home_team_id, away_team_id, date);

-- Index for games needing score updates (NULL home_score with date filter)
-- Pattern: WHERE date <= X AND home_score IS NULL
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_games_unscored
ON games(date) WHERE home_score IS NULL;

-- ============================================
-- PREDICTIONS TABLE - Composite Indexes
-- ============================================

-- Composite index for getting latest prediction per game
-- Pattern: WHERE game_id = X ORDER BY created_at DESC LIMIT 1
-- This is the most common predictions query pattern
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_predictions_game_created
ON predictions(game_id, created_at DESC);

-- ============================================
-- AI_ANALYSIS TABLE - Composite Indexes
-- ============================================

-- Composite index for getting latest analysis per game (any provider)
-- Pattern: WHERE game_id = X ORDER BY created_at DESC LIMIT 1
-- Used in LATERAL subqueries in today_games and upcoming_games views
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_analysis_game_created
ON ai_analysis(game_id, created_at DESC);

-- Composite index for getting latest analysis by provider
-- Pattern: WHERE game_id = X AND ai_provider = Y ORDER BY created_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_analysis_game_provider_created
ON ai_analysis(game_id, ai_provider, created_at DESC);

-- ============================================
-- SPREADS TABLE - Composite Indexes
-- ============================================

-- Composite index for getting latest spread per game
-- Pattern: WHERE game_id = X ORDER BY captured_at DESC LIMIT 1
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spreads_game_captured
ON spreads(game_id, captured_at DESC);

-- ============================================
-- KENPOM_RATINGS TABLE - Additional Indexes
-- ============================================

-- Composite index for the latest_kenpom_ratings view
-- Pattern: DISTINCT ON (team_id, season) ORDER BY team_id, season, captured_at DESC
-- Existing: idx_kenpom_team_season covers (team_id, season)
-- Adding captured_at to support the ORDER BY in DISTINCT ON
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_kenpom_team_season_captured
ON kenpom_ratings(team_id, season, captured_at DESC);

-- ============================================
-- HASLAMETRICS_RATINGS TABLE - Additional Indexes
-- ============================================

-- Composite index for the latest_haslametrics_ratings view
-- Pattern: DISTINCT ON (team_id, season) ORDER BY team_id, season, captured_at DESC
-- Existing: idx_hasla_team_season covers (team_id, season)
-- Adding captured_at to support the ORDER BY in DISTINCT ON
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hasla_team_season_captured
ON haslametrics_ratings(team_id, season, captured_at DESC);

-- ============================================
-- RANKINGS TABLE - Additional Indexes
-- ============================================

-- Composite index for LATERAL subqueries in views
-- Pattern: WHERE team_id = X AND season = Y ORDER BY week DESC LIMIT 1
-- Used extensively in today_games and upcoming_games views
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rankings_team_season_week
ON rankings(team_id, season, week DESC);

-- Index for getting current week rankings
-- Pattern: WHERE season = X AND week = (SELECT MAX(week)...)
-- Existing: idx_rankings_season_week covers this
-- Adding poll_type for common filtered queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rankings_season_week_poll
ON rankings(season, week, poll_type);

-- ============================================
-- BET_RESULTS TABLE - Composite Indexes
-- ============================================

-- Composite index for season performance calculations
-- Pattern: JOIN games WHERE season = X AND result != 'pending'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bet_results_result_game
ON bet_results(result, game_id);

-- ============================================
-- FOREIGN KEY COLUMNS - Ensure Indexes Exist
-- ============================================

-- Foreign keys should have indexes for JOIN performance
-- Most already exist, but verifying coverage:

-- spreads.game_id - already has idx_spreads_game
-- predictions.game_id - already has idx_predictions_game
-- ai_analysis.game_id - already has idx_ai_analysis_game
-- rankings.team_id - covered by idx_rankings_team_season
-- bet_results.game_id - already has idx_bet_results_game
-- bet_results.prediction_id - needs index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bet_results_prediction
ON bet_results(prediction_id);

-- kenpom_ratings.team_id - covered by idx_kenpom_team_season
-- haslametrics_ratings.team_id - covered by idx_hasla_team_season

-- ============================================
-- TEAMS TABLE - Additional Indexes for Lookups
-- ============================================

-- Index for team name lookups during data import
-- Pattern: WHERE normalized_name = X (case-insensitive matching)
-- Existing: idx_teams_normalized covers this
-- Adding conference filter for queries like "all Big Ten teams"
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_teams_conference_name
ON teams(conference, normalized_name);

-- ============================================
-- ANALYZE TABLES
-- ============================================
-- Update statistics for query planner after adding indexes

ANALYZE games;
ANALYZE teams;
ANALYZE predictions;
ANALYZE ai_analysis;
ANALYZE spreads;
ANALYZE kenpom_ratings;
ANALYZE haslametrics_ratings;
ANALYZE rankings;
ANALYZE bet_results;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON INDEX idx_games_date_status IS 'Composite index for filtering games by date and status - covers upcoming/today games queries';
COMMENT ON INDEX idx_games_teams_date IS 'Composite index for finding specific matchups by teams and date - used in odds data processing';
COMMENT ON INDEX idx_games_unscored IS 'Partial index for finding games needing score updates - filters to NULL home_score';
COMMENT ON INDEX idx_predictions_game_created IS 'Composite index for getting latest prediction per game - descending created_at for LIMIT 1 queries';
COMMENT ON INDEX idx_ai_analysis_game_created IS 'Composite index for LATERAL subqueries getting latest analysis per game';
COMMENT ON INDEX idx_ai_analysis_game_provider_created IS 'Composite index for getting latest AI analysis by provider - supports dual-provider system';
COMMENT ON INDEX idx_spreads_game_captured IS 'Composite index for getting latest spread per game - descending captured_at for LIMIT 1 queries';
COMMENT ON INDEX idx_kenpom_team_season_captured IS 'Composite index supporting latest_kenpom_ratings view DISTINCT ON query';
COMMENT ON INDEX idx_hasla_team_season_captured IS 'Composite index supporting latest_haslametrics_ratings view DISTINCT ON query';
COMMENT ON INDEX idx_rankings_team_season_week IS 'Composite index for LATERAL subqueries in views getting latest ranking per team/season';
COMMENT ON INDEX idx_rankings_season_week_poll IS 'Composite index for filtered ranking queries by poll type';
COMMENT ON INDEX idx_bet_results_result_game IS 'Composite index for season performance aggregation queries';
COMMENT ON INDEX idx_bet_results_prediction IS 'Foreign key index for prediction_id column';
COMMENT ON INDEX idx_teams_conference_name IS 'Composite index for conference-filtered team lookups';
