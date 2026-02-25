-- Tournament Bracket Data Model
-- Adds tournament metadata, seeding, and bracket picks
-- for March Madness bracket analysis

-- ============================================
-- TOURNAMENTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS tournaments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT 'NCAA Tournament',
    status TEXT NOT NULL DEFAULT 'upcoming',
    selection_sunday_date DATE,
    start_date DATE,
    end_date DATE,
    champion_team_id UUID REFERENCES teams(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN tournaments.status IS 'upcoming, bracket_set, in_progress, completed';
COMMENT ON TABLE tournaments IS 'NCAA Tournament metadata by season';

-- ============================================
-- TOURNAMENT SEEDS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS tournament_seeds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    team_id UUID NOT NULL REFERENCES teams(id),
    seed INTEGER NOT NULL CHECK (seed BETWEEN 1 AND 16),
    region TEXT NOT NULL,
    is_play_in BOOLEAN DEFAULT FALSE,
    play_in_matchup INTEGER CHECK (play_in_matchup IN (1, 2)),
    eliminated_in_round TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tournament_id, team_id),
    UNIQUE(tournament_id, region, seed, play_in_matchup)
);

COMMENT ON COLUMN tournament_seeds.region IS 'East, West, South, Midwest';
COMMENT ON COLUMN tournament_seeds.seed IS '1-16 within the region';
COMMENT ON COLUMN tournament_seeds.is_play_in IS 'True for First Four teams sharing a seed slot';
COMMENT ON COLUMN tournament_seeds.play_in_matchup IS '1 or 2 for play-in teams, NULL otherwise';
COMMENT ON COLUMN tournament_seeds.eliminated_in_round IS 'first_four, round_64, round_32, sweet_16, elite_8, final_4, championship, NULL if alive or champion';
COMMENT ON TABLE tournament_seeds IS 'Tournament seed and region assignments for each team';

-- ============================================
-- BRACKET PICKS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS bracket_picks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    game_id UUID REFERENCES games(id) ON DELETE CASCADE,
    round TEXT NOT NULL,
    region TEXT,
    picked_team_id UUID NOT NULL REFERENCES teams(id),
    is_correct BOOLEAN,
    confidence_score DECIMAL(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
    reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tournament_id, game_id)
);

COMMENT ON COLUMN bracket_picks.round IS 'first_four, round_64, round_32, sweet_16, elite_8, final_4, championship';
COMMENT ON COLUMN bracket_picks.region IS 'East, West, South, Midwest, NULL for Final Four/Championship';
COMMENT ON COLUMN bracket_picks.is_correct IS 'NULL until graded, then TRUE/FALSE';
COMMENT ON TABLE bracket_picks IS 'Developer bracket predictions for tournament games';

-- ============================================
-- INDEXES
-- ============================================
CREATE INDEX IF NOT EXISTS idx_tournament_seeds_tournament ON tournament_seeds(tournament_id);
CREATE INDEX IF NOT EXISTS idx_tournament_seeds_team ON tournament_seeds(team_id);
CREATE INDEX IF NOT EXISTS idx_tournament_seeds_region_seed ON tournament_seeds(tournament_id, region, seed);
CREATE INDEX IF NOT EXISTS idx_bracket_picks_tournament ON bracket_picks(tournament_id);
CREATE INDEX IF NOT EXISTS idx_bracket_picks_game ON bracket_picks(game_id);
CREATE INDEX IF NOT EXISTS idx_bracket_picks_round ON bracket_picks(tournament_id, round);

-- Tournament games lookup (leverages existing games table)
CREATE INDEX IF NOT EXISTS idx_games_tournament_round
ON games(tournament_round, date)
WHERE is_tournament = TRUE;

-- ============================================
-- TRIGGERS (reuse existing update_updated_at function)
-- ============================================
CREATE TRIGGER tournaments_updated_at
    BEFORE UPDATE ON tournaments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tournament_seeds_updated_at
    BEFORE UPDATE ON tournament_seeds
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER bracket_picks_updated_at
    BEFORE UPDATE ON bracket_picks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- VIEWS
-- ============================================

-- Bracket view: tournament games with seeds and picks
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
LEFT JOIN tournament_seeds hs ON hs.team_id = g.home_team_id
    AND hs.tournament_id = (
        SELECT t.id FROM tournaments t WHERE t.season = g.season LIMIT 1
    )
LEFT JOIN tournament_seeds aws ON aws.team_id = g.away_team_id
    AND aws.tournament_id = hs.tournament_id
LEFT JOIN LATERAL (
    SELECT * FROM spreads
    WHERE game_id = g.id
    ORDER BY captured_at DESC
    LIMIT 1
) s ON TRUE
LEFT JOIN bracket_picks bp ON bp.game_id = g.id
LEFT JOIN teams pt ON bp.picked_team_id = pt.id
WHERE g.is_tournament = TRUE
ORDER BY g.date, g.tip_time, g.id;

-- Region summary view
CREATE OR REPLACE VIEW tournament_region_summary AS
SELECT
    t.season,
    ts.region,
    ts.seed,
    tm.name AS team_name,
    tm.conference,
    ts.is_play_in,
    ts.eliminated_in_round,
    CASE
        WHEN ts.eliminated_in_round IS NULL AND t.status != 'completed' THEN TRUE
        WHEN t.champion_team_id = ts.team_id THEN TRUE
        ELSE FALSE
    END AS is_alive
FROM tournament_seeds ts
JOIN tournaments t ON ts.tournament_id = t.id
JOIN teams tm ON ts.team_id = tm.id
ORDER BY t.season DESC, ts.region, ts.seed, ts.play_in_matchup NULLS FIRST;
