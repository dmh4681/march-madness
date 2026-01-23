-- Add prediction market flags to today_games and upcoming_games views
-- This migration adds has_prediction_data and has_arbitrage_signal columns

-- Drop and recreate today_games view
DROP VIEW IF EXISTS today_games CASCADE;

CREATE OR REPLACE VIEW today_games AS
SELECT
    g.id,
    g.date,
    g.date as tip_time,
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

    -- Use AI analysis if available (Claude preferred over Grok), otherwise baseline prediction
    COALESCE(claude.confidence_score, grok.confidence_score, p.predicted_home_cover_prob) as predicted_home_cover_prob,
    CASE
        WHEN claude.id IS NOT NULL THEN
            CASE
                WHEN claude.confidence_score >= 0.7 THEN 'high'
                WHEN claude.confidence_score >= 0.5 THEN 'medium'
                ELSE 'low'
            END
        WHEN grok.id IS NOT NULL THEN
            CASE
                WHEN grok.confidence_score >= 0.7 THEN 'high'
                WHEN grok.confidence_score >= 0.5 THEN 'medium'
                ELSE 'low'
            END
        ELSE p.confidence_tier
    END as confidence_tier,
    COALESCE(claude.recommended_bet, grok.recommended_bet, p.recommended_bet) as recommended_bet,

    -- EDGE CALCULATION: (AI_Confidence - Market_Implied_Probability) × 100
    COALESCE(
        CASE WHEN claude.id IS NOT NULL THEN
            (claude.confidence_score -
                CASE
                    WHEN claude.recommended_bet IN ('home_spread', 'away_spread') THEN
                        CASE
                            WHEN claude.recommended_bet = 'home_spread' THEN american_odds_to_implied_prob(s.home_spread_odds)
                            ELSE american_odds_to_implied_prob(s.away_spread_odds)
                        END
                    WHEN claude.recommended_bet IN ('home_ml', 'away_ml') THEN
                        CASE
                            WHEN claude.recommended_bet = 'home_ml' THEN american_odds_to_implied_prob(s.home_ml)
                            ELSE american_odds_to_implied_prob(s.away_ml)
                        END
                    ELSE 0.524
                END
            ) * 100
        END,
        CASE WHEN grok.id IS NOT NULL THEN
            (grok.confidence_score -
                CASE
                    WHEN grok.recommended_bet IN ('home_spread', 'away_spread') THEN
                        CASE
                            WHEN grok.recommended_bet = 'home_spread' THEN american_odds_to_implied_prob(s.home_spread_odds)
                            ELSE american_odds_to_implied_prob(s.away_spread_odds)
                        END
                    WHEN grok.recommended_bet IN ('home_ml', 'away_ml') THEN
                        CASE
                            WHEN grok.recommended_bet = 'home_ml' THEN american_odds_to_implied_prob(s.home_ml)
                            ELSE american_odds_to_implied_prob(s.away_ml)
                        END
                    ELSE 0.524
                END
            ) * 100
        END,
        p.edge_pct
    ) as edge_pct,

    -- AI analysis flags
    (claude.id IS NOT NULL OR grok.id IS NOT NULL) as has_ai_analysis,
    (claude.id IS NOT NULL) as has_claude_analysis,
    (grok.id IS NOT NULL) as has_grok_analysis,

    -- Prediction market flags (check both game-level and team-level markets)
    (EXISTS (
        SELECT 1 FROM prediction_markets pm
        WHERE pm.status = 'open'
        AND (pm.game_id = g.id OR pm.team_id = ht.id OR pm.team_id = at.id)
    )) as has_prediction_data,
    (EXISTS (
        SELECT 1 FROM arbitrage_opportunities ao
        WHERE ao.game_id = g.id
        AND ao.is_actionable = true
        AND ao.captured_at > NOW() - INTERVAL '24 hours'
    )) as has_arbitrage_signal

FROM games g
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams at ON g.away_team_id = at.id
LEFT JOIN LATERAL (
    SELECT home_spread, home_ml, away_ml, over_under, home_spread_odds, away_spread_odds
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
LEFT JOIN LATERAL (
    SELECT id, recommended_bet, confidence_score
    FROM ai_analysis
    WHERE game_id = g.id AND ai_provider = 'claude'
    ORDER BY created_at DESC
    LIMIT 1
) claude ON true
LEFT JOIN LATERAL (
    SELECT id, recommended_bet, confidence_score
    FROM ai_analysis
    WHERE game_id = g.id AND ai_provider = 'grok'
    ORDER BY created_at DESC
    LIMIT 1
) grok ON true
WHERE g.date = CURRENT_DATE
ORDER BY g.date, ht.name;


-- Drop and recreate upcoming_games view
DROP VIEW IF EXISTS upcoming_games CASCADE;

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

    -- Use AI analysis if available (Claude preferred over Grok), otherwise baseline prediction
    COALESCE(claude.confidence_score, grok.confidence_score, p.predicted_home_cover_prob) as predicted_home_cover_prob,
    CASE
        WHEN claude.id IS NOT NULL THEN
            CASE
                WHEN claude.confidence_score >= 0.7 THEN 'high'
                WHEN claude.confidence_score >= 0.5 THEN 'medium'
                ELSE 'low'
            END
        WHEN grok.id IS NOT NULL THEN
            CASE
                WHEN grok.confidence_score >= 0.7 THEN 'high'
                WHEN grok.confidence_score >= 0.5 THEN 'medium'
                ELSE 'low'
            END
        ELSE p.confidence_tier
    END as confidence_tier,
    COALESCE(claude.recommended_bet, grok.recommended_bet, p.recommended_bet) as recommended_bet,

    -- EDGE CALCULATION
    COALESCE(
        CASE WHEN claude.id IS NOT NULL THEN
            (claude.confidence_score -
                CASE
                    WHEN claude.recommended_bet IN ('home_spread', 'away_spread') THEN
                        CASE
                            WHEN claude.recommended_bet = 'home_spread' THEN american_odds_to_implied_prob(s.home_spread_odds)
                            ELSE american_odds_to_implied_prob(s.away_spread_odds)
                        END
                    WHEN claude.recommended_bet IN ('home_ml', 'away_ml') THEN
                        CASE
                            WHEN claude.recommended_bet = 'home_ml' THEN american_odds_to_implied_prob(s.home_ml)
                            ELSE american_odds_to_implied_prob(s.away_ml)
                        END
                    ELSE 0.524
                END
            ) * 100
        END,
        CASE WHEN grok.id IS NOT NULL THEN
            (grok.confidence_score -
                CASE
                    WHEN grok.recommended_bet IN ('home_spread', 'away_spread') THEN
                        CASE
                            WHEN grok.recommended_bet = 'home_spread' THEN american_odds_to_implied_prob(s.home_spread_odds)
                            ELSE american_odds_to_implied_prob(s.away_spread_odds)
                        END
                    WHEN grok.recommended_bet IN ('home_ml', 'away_ml') THEN
                        CASE
                            WHEN grok.recommended_bet = 'home_ml' THEN american_odds_to_implied_prob(s.home_ml)
                            ELSE american_odds_to_implied_prob(s.away_ml)
                        END
                    ELSE 0.524
                END
            ) * 100
        END,
        p.edge_pct
    ) as edge_pct,

    -- AI analysis flags
    (claude.id IS NOT NULL OR grok.id IS NOT NULL) as has_ai_analysis,
    (claude.id IS NOT NULL) as has_claude_analysis,
    (grok.id IS NOT NULL) as has_grok_analysis,

    -- Prediction market flags (check both game-level and team-level markets)
    (EXISTS (
        SELECT 1 FROM prediction_markets pm
        WHERE pm.status = 'open'
        AND (pm.game_id = g.id OR pm.team_id = ht.id OR pm.team_id = at.id)
    )) as has_prediction_data,
    (EXISTS (
        SELECT 1 FROM arbitrage_opportunities ao
        WHERE ao.game_id = g.id
        AND ao.is_actionable = true
        AND ao.captured_at > NOW() - INTERVAL '24 hours'
    )) as has_arbitrage_signal

FROM games g
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams at ON g.away_team_id = at.id
LEFT JOIN LATERAL (
    SELECT home_spread, home_ml, away_ml, over_under, home_spread_odds, away_spread_odds
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
LEFT JOIN LATERAL (
    SELECT id, recommended_bet, confidence_score
    FROM ai_analysis
    WHERE game_id = g.id AND ai_provider = 'claude'
    ORDER BY created_at DESC
    LIMIT 1
) claude ON true
LEFT JOIN LATERAL (
    SELECT id, recommended_bet, confidence_score
    FROM ai_analysis
    WHERE game_id = g.id AND ai_provider = 'grok'
    ORDER BY created_at DESC
    LIMIT 1
) grok ON true
WHERE g.date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
ORDER BY g.date, ht.name;


-- Grant access
GRANT SELECT ON today_games TO authenticated;
GRANT SELECT ON today_games TO anon;
GRANT SELECT ON upcoming_games TO authenticated;
GRANT SELECT ON upcoming_games TO anon;

COMMENT ON VIEW today_games IS 'Today games with AI analysis, predictions, and prediction market flags';
COMMENT ON VIEW upcoming_games IS 'Upcoming games (7 days) with AI analysis, predictions, and prediction market flags';
