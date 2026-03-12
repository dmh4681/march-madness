-- Bracket Query Optimization
-- =====================================================
-- Addresses performance issues in tournament_bracket view
-- and adds covering indexes for bracket table queries.
--
-- Key problem: The tournament_bracket view uses a correlated
-- subquery (SELECT t.id FROM tournaments WHERE season = g.season)
-- that re-executes once per qualifying game row.
--
-- Fix: Replace correlated subquery with a direct JOIN on tournaments.
-- This allows the planner to use a hash/merge join instead of
-- a nested-loop correlated scan.

-- ============================================
-- SECTION 1: Covering Indexes for Bracket Tables
-- ============================================

-- tournaments(season) already has an implicit unique index.
-- Add an explicit index to make intent clear and allow INCLUDE.
CREATE INDEX IF NOT EXISTS idx_tournaments_season
ON tournaments(season)
INCLUDE (id, status);

COMMENT ON INDEX idx_tournaments_season IS 'Season lookup for tournament_bracket view JOIN; INCLUDE id avoids heap fetch';

-- tournament_seeds: covering index for the view JOIN pattern
-- Pattern: WHERE tournament_id = X AND team_id = Y
-- INCLUDE seed/region so view can satisfy columns from index only.
CREATE INDEX IF NOT EXISTS idx_tournament_seeds_tid_team_covering
ON tournament_seeds(tournament_id, team_id)
INCLUDE (seed, region, is_play_in, eliminated_in_round);

COMMENT ON INDEX idx_tournament_seeds_tid_team_covering IS 'Covering index for tournament_bracket view seed lookups by team';

-- tournament_seeds: covering index for region summary view
-- Pattern: ORDER BY season DESC, region, seed
CREATE INDEX IF NOT EXISTS idx_tournament_seeds_region_summary
ON tournament_seeds(tournament_id, region, seed, play_in_matchup)
INCLUDE (team_id, is_play_in, eliminated_in_round);

COMMENT ON INDEX idx_tournament_seeds_region_summary IS 'Covering index for tournament_region_summary view ORDER BY pattern';

-- bracket_picks: covering index for game lookup in view
-- Pattern: WHERE game_id = X (one pick per game)
CREATE INDEX IF NOT EXISTS idx_bracket_picks_game_covering
ON bracket_picks(game_id)
INCLUDE (tournament_id, round, region, picked_team_id, is_correct, confidence_score, reasoning);

COMMENT ON INDEX idx_bracket_picks_game_covering IS 'Covering index for bracket_picks lookup by game in tournament_bracket view';

-- bracket_picks: index for grading pipeline
-- Pattern: WHERE tournament_id = X AND is_correct IS NULL
CREATE INDEX IF NOT EXISTS idx_bracket_picks_ungraded
ON bracket_picks(tournament_id, round)
WHERE is_correct IS NULL;

COMMENT ON INDEX idx_bracket_picks_ungraded IS 'Partial index for grading pipeline - ungraded picks only';

-- tournament_seeds: partial index for alive teams
-- Pattern: WHERE tournament_id = X AND eliminated_in_round IS NULL
CREATE INDEX IF NOT EXISTS idx_tournament_seeds_alive
ON tournament_seeds(tournament_id, region, seed)
WHERE eliminated_in_round IS NULL;

COMMENT ON INDEX idx_tournament_seeds_alive IS 'Partial index for alive teams - used in grading and region summary';

-- ============================================
-- SECTION 2: Rewrite tournament_bracket View
-- ============================================
-- Replace correlated subquery with a direct JOIN on tournaments.
-- Before: hs.tournament_id = (SELECT t.id FROM tournaments t WHERE t.season = g.season LIMIT 1)
-- After:  JOIN tournaments t ON t.season = g.season
--         ...hs.tournament_id = t.id
--
-- This allows the planner to execute the join once rather than
-- running a subquery scan for each game row.

CREATE OR REPLACE VIEW tournament_bracket AS
SELECT
    g.id AS game_id,
    g.date,
    g.tip_time,
    g.tournament_round,
    g.status AS game_status,
    g.home_score,
    g.away_score,
    g.neutral_site,
    g.season,
    ht.name AS home_team,
    ht.conference AS home_conference,
    hs.seed AS home_seed,
    hs.region AS home_region,
    awt.name AS away_team,
    awt.conference AS away_conference,
    aws.seed AS away_seed,
    aws.region AS away_region,
    s.home_spread,
    s.home_ml,
    s.away_ml,
    s.over_under,
    bp.picked_team_id,
    pt.name AS picked_team,
    bp.is_correct,
    bp.confidence_score AS pick_confidence,
    bp.reasoning AS pick_reasoning
FROM games g
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams awt ON g.away_team_id = awt.id
LEFT JOIN tournaments t ON t.season = g.season
LEFT JOIN tournament_seeds hs ON hs.tournament_id = t.id
    AND hs.team_id = g.home_team_id
LEFT JOIN tournament_seeds aws ON aws.tournament_id = t.id
    AND aws.team_id = g.away_team_id
LEFT JOIN LATERAL (
    SELECT home_spread, home_ml, away_ml, over_under, home_spread_odds, away_spread_odds
    FROM spreads
    WHERE game_id = g.id
    ORDER BY captured_at DESC
    LIMIT 1
) s ON TRUE
LEFT JOIN bracket_picks bp ON bp.game_id = g.id
LEFT JOIN teams pt ON bp.picked_team_id = pt.id
WHERE g.is_tournament = TRUE
ORDER BY g.date, g.tip_time, g.id;

-- ============================================
-- SECTION 3: Analyze New Tables
-- ============================================

ANALYZE tournaments;
ANALYZE tournament_seeds;
ANALYZE bracket_picks;
