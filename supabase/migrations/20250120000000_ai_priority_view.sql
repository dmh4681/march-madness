-- Update today_games view to prioritize AI analysis over baseline predictions
-- When AI analysis exists, use its recommendation; otherwise fall back to baseline
-- Claude is primary AI, Grok is secondary. If both exist, use Claude's pick.
--
-- EDGE CALCULATION (Scientific):
-- Edge % = (AI_Confidence - Market_Implied_Probability) × 100
--
-- Market Implied Probability from American Odds:
--   Negative odds (e.g., -150): |odds| / (|odds| + 100) = 60%
--   Positive odds (e.g., +150): 100 / (odds + 100) = 40%
--
-- For spread bets: use spread odds (typically -110 = 52.38%)
-- For moneyline bets: use actual moneyline odds

DROP VIEW IF EXISTS today_games CASCADE;
DROP VIEW IF EXISTS upcoming_games CASCADE;

-- Helper function to convert American odds to implied probability
CREATE OR REPLACE FUNCTION american_odds_to_implied_prob(odds INTEGER)
RETURNS DECIMAL AS $$
BEGIN
    IF odds IS NULL THEN
        RETURN 0.5; -- Default to 50% if no odds
    ELSIF odds < 0 THEN
        -- Negative odds: |odds| / (|odds| + 100)
        RETURN ABS(odds)::DECIMAL / (ABS(odds) + 100);
    ELSE
        -- Positive odds: 100 / (odds + 100)
        RETURN 100.0 / (odds + 100);
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION american_odds_to_implied_prob IS 'Converts American odds to implied probability. -110 → 0.524, +150 → 0.40, -150 → 0.60';

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
    -- Uses actual odds based on bet type (spread vs moneyline)
    COALESCE(
        CASE WHEN claude.id IS NOT NULL THEN
            (claude.confidence_score -
                CASE
                    -- Spread bets: use spread odds
                    WHEN claude.recommended_bet IN ('home_spread', 'away_spread') THEN
                        CASE
                            WHEN claude.recommended_bet = 'home_spread' THEN american_odds_to_implied_prob(s.home_spread_odds)
                            ELSE american_odds_to_implied_prob(s.away_spread_odds)
                        END
                    -- Moneyline bets: use ML odds
                    WHEN claude.recommended_bet IN ('home_ml', 'away_ml') THEN
                        CASE
                            WHEN claude.recommended_bet = 'home_ml' THEN american_odds_to_implied_prob(s.home_ml)
                            ELSE american_odds_to_implied_prob(s.away_ml)
                        END
                    -- Over/under or pass: default to 52.4% (standard -110)
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

    -- Flags to indicate which AI analyses exist
    (claude.id IS NOT NULL OR grok.id IS NOT NULL) as has_ai_analysis,
    (claude.id IS NOT NULL) as has_claude_analysis,
    (grok.id IS NOT NULL) as has_grok_analysis

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


-- Same for upcoming_games view (Claude preferred over Grok)
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

    -- Flags to indicate which AI analyses exist
    (claude.id IS NOT NULL OR grok.id IS NOT NULL) as has_ai_analysis,
    (claude.id IS NOT NULL) as has_claude_analysis,
    (grok.id IS NOT NULL) as has_grok_analysis

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
