-- Create a view for today's games with all relevant data
-- This makes it easy for the frontend to fetch everything in one query

-- Drop existing views first (they may have different column types)
DROP VIEW IF EXISTS today_games CASCADE;
DROP VIEW IF EXISTS upcoming_games CASCADE;

CREATE OR REPLACE VIEW today_games AS
SELECT
    g.id,
    g.date,
    g.date as tip_time,  -- Would be actual tip time if we had it
    g.season,
    g.is_conference_game,
    g.home_score,
    g.away_score,
    g.status,

    -- Home team info
    ht.name as home_team,
    ht.conference as home_conference,
    ht.id as home_team_id,

    -- Away team info
    at.name as away_team,
    at.conference as away_conference,
    at.id as away_team_id,

    -- Latest spread data
    s.home_spread,
    s.home_ml,
    s.away_ml,
    s.over_under,

    -- Rankings
    hr.rank as home_rank,
    ar.rank as away_rank,

    -- Latest prediction
    p.predicted_home_cover_prob,
    p.confidence_tier,
    p.recommended_bet,
    p.edge_pct

FROM games g
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams at ON g.away_team_id = at.id
LEFT JOIN LATERAL (
    SELECT home_spread, home_ml, away_ml, over_under
    FROM spreads
    WHERE game_id = g.id
    ORDER BY captured_at DESC
    LIMIT 1
) s ON true
LEFT JOIN LATERAL (
    SELECT rank
    FROM rankings
    WHERE team_id = ht.id AND season = g.season
    ORDER BY week DESC
    LIMIT 1
) hr ON true
LEFT JOIN LATERAL (
    SELECT rank
    FROM rankings
    WHERE team_id = at.id AND season = g.season
    ORDER BY week DESC
    LIMIT 1
) ar ON true
LEFT JOIN LATERAL (
    SELECT predicted_home_cover_prob, confidence_tier, recommended_bet, edge_pct
    FROM predictions
    WHERE game_id = g.id
    ORDER BY created_at DESC
    LIMIT 1
) p ON true
WHERE g.date = CURRENT_DATE
ORDER BY g.date, ht.name;


-- Create a similar view for upcoming games (next 7 days)
CREATE OR REPLACE VIEW upcoming_games AS
SELECT
    g.id,
    g.date,
    g.date as tip_time,
    g.season,
    g.is_conference_game,
    g.home_score,
    g.away_score,
    g.status,

    ht.name as home_team,
    ht.conference as home_conference,
    ht.id as home_team_id,

    at.name as away_team,
    at.conference as away_conference,
    at.id as away_team_id,

    s.home_spread,
    s.home_ml,
    s.away_ml,
    s.over_under,

    hr.rank as home_rank,
    ar.rank as away_rank,

    p.predicted_home_cover_prob,
    p.confidence_tier,
    p.recommended_bet,
    p.edge_pct

FROM games g
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams at ON g.away_team_id = at.id
LEFT JOIN LATERAL (
    SELECT home_spread, home_ml, away_ml, over_under
    FROM spreads
    WHERE game_id = g.id
    ORDER BY captured_at DESC
    LIMIT 1
) s ON true
LEFT JOIN LATERAL (
    SELECT rank
    FROM rankings
    WHERE team_id = ht.id AND season = g.season
    ORDER BY week DESC
    LIMIT 1
) hr ON true
LEFT JOIN LATERAL (
    SELECT rank
    FROM rankings
    WHERE team_id = at.id AND season = g.season
    ORDER BY week DESC
    LIMIT 1
) ar ON true
LEFT JOIN LATERAL (
    SELECT predicted_home_cover_prob, confidence_tier, recommended_bet, edge_pct
    FROM predictions
    WHERE game_id = g.id
    ORDER BY created_at DESC
    LIMIT 1
) p ON true
WHERE g.date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
ORDER BY g.date, ht.name;


-- Grant access to these views
GRANT SELECT ON today_games TO authenticated;
GRANT SELECT ON today_games TO anon;
GRANT SELECT ON upcoming_games TO authenticated;
GRANT SELECT ON upcoming_games TO anon;
