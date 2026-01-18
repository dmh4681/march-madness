-- Conference Contrarian Database Schema
-- Supabase Migration: Initial Setup

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TEAMS TABLE
-- ============================================
CREATE TABLE teams (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL UNIQUE,
  mascot TEXT,
  conference TEXT,
  is_power_conference BOOLEAN DEFAULT FALSE,
  logo_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Power conferences for quick filtering
COMMENT ON COLUMN teams.is_power_conference IS 'ACC, Big Ten, Big 12, SEC, Big East, Pac-12';

-- ============================================
-- GAMES TABLE
-- ============================================
CREATE TABLE games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  external_id TEXT UNIQUE,
  date DATE NOT NULL,
  tip_time TIMESTAMPTZ,
  season INTEGER NOT NULL,
  home_team_id UUID REFERENCES teams(id),
  away_team_id UUID REFERENCES teams(id),
  home_score INTEGER,
  away_score INTEGER,
  is_conference_game BOOLEAN DEFAULT FALSE,
  is_tournament BOOLEAN DEFAULT FALSE,
  tournament_round TEXT,
  venue TEXT,
  neutral_site BOOLEAN DEFAULT FALSE,
  status TEXT DEFAULT 'scheduled',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN games.status IS 'scheduled, in_progress, final, postponed, cancelled';
COMMENT ON COLUMN games.tournament_round IS 'first_four, round_64, round_32, sweet_16, elite_8, final_4, championship';

-- ============================================
-- SPREADS TABLE
-- ============================================
CREATE TABLE spreads (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  game_id UUID REFERENCES games(id) ON DELETE CASCADE,
  captured_at TIMESTAMPTZ DEFAULT NOW(),
  home_spread DECIMAL(5,1),
  away_spread DECIMAL(5,1),
  home_spread_odds INTEGER DEFAULT -110,
  away_spread_odds INTEGER DEFAULT -110,
  home_ml INTEGER,
  away_ml INTEGER,
  over_under DECIMAL(5,1),
  over_odds INTEGER DEFAULT -110,
  under_odds INTEGER DEFAULT -110,
  source TEXT DEFAULT 'odds-api',
  is_opening_line BOOLEAN DEFAULT FALSE,
  is_closing_line BOOLEAN DEFAULT FALSE
);

COMMENT ON COLUMN spreads.home_ml IS 'Moneyline odds for home team (e.g., -150, +120)';

-- ============================================
-- RANKINGS TABLE
-- ============================================
CREATE TABLE rankings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
  season INTEGER NOT NULL,
  week INTEGER NOT NULL,
  poll_date DATE,
  rank INTEGER,
  previous_rank INTEGER,
  first_place_votes INTEGER,
  total_points INTEGER,
  poll_type TEXT DEFAULT 'ap',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(team_id, season, week, poll_type)
);

COMMENT ON COLUMN rankings.week IS '0 = preseason, 1-18 = regular season weeks';
COMMENT ON COLUMN rankings.poll_type IS 'ap, coaches, kenpom, net';

-- ============================================
-- PREDICTIONS TABLE
-- ============================================
CREATE TABLE predictions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  game_id UUID REFERENCES games(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  model_name TEXT NOT NULL,
  model_version TEXT DEFAULT '1.0',
  spread_at_prediction DECIMAL(5,1),
  predicted_home_cover_prob DECIMAL(4,3),
  predicted_away_cover_prob DECIMAL(4,3),
  predicted_home_win_prob DECIMAL(4,3),
  predicted_margin DECIMAL(5,1),
  confidence_tier TEXT,
  recommended_bet TEXT,
  edge_pct DECIMAL(5,2),
  kelly_fraction DECIMAL(4,3),
  features_json JSONB
);

COMMENT ON COLUMN predictions.confidence_tier IS 'high, medium, low, pass';
COMMENT ON COLUMN predictions.recommended_bet IS 'home_spread, away_spread, home_ml, away_ml, over, under, pass';
COMMENT ON COLUMN predictions.features_json IS 'Stored feature values for debugging/analysis';

-- ============================================
-- AI ANALYSIS TABLE
-- ============================================
CREATE TABLE ai_analysis (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  game_id UUID REFERENCES games(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  ai_provider TEXT NOT NULL,
  model_used TEXT,
  analysis_type TEXT NOT NULL,
  prompt_hash TEXT,
  response TEXT,
  structured_analysis JSONB,
  recommended_bet TEXT,
  confidence_score DECIMAL(3,2),
  key_factors TEXT[],
  reasoning TEXT,
  tokens_used INTEGER
);

COMMENT ON COLUMN ai_analysis.ai_provider IS 'claude, grok, openai';
COMMENT ON COLUMN ai_analysis.analysis_type IS 'matchup, edge_detection, summary, injury_impact';

-- ============================================
-- BET RESULTS TABLE
-- ============================================
CREATE TABLE bet_results (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prediction_id UUID REFERENCES predictions(id),
  game_id UUID REFERENCES games(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  bet_type TEXT NOT NULL,
  side TEXT NOT NULL,
  spread_at_bet DECIMAL(5,1),
  odds_at_bet INTEGER DEFAULT -110,
  result TEXT,
  units_wagered DECIMAL(5,2) DEFAULT 1.0,
  units_won DECIMAL(6,2),
  actual_margin INTEGER,
  graded_at TIMESTAMPTZ
);

COMMENT ON COLUMN bet_results.bet_type IS 'spread, ml, over, under';
COMMENT ON COLUMN bet_results.side IS 'home, away';
COMMENT ON COLUMN bet_results.result IS 'win, loss, push, pending';

-- ============================================
-- PERFORMANCE SUMMARY TABLE
-- ============================================
CREATE TABLE performance_summary (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  date DATE NOT NULL UNIQUE,
  season INTEGER NOT NULL,
  total_bets INTEGER DEFAULT 0,
  wins INTEGER DEFAULT 0,
  losses INTEGER DEFAULT 0,
  pushes INTEGER DEFAULT 0,
  units_wagered DECIMAL(8,2) DEFAULT 0,
  units_won DECIMAL(8,2) DEFAULT 0,
  roi_pct DECIMAL(6,2),
  high_confidence_record TEXT,
  medium_confidence_record TEXT,
  low_confidence_record TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================
CREATE INDEX idx_teams_normalized ON teams(normalized_name);
CREATE INDEX idx_teams_conference ON teams(conference);

CREATE INDEX idx_games_date ON games(date);
CREATE INDEX idx_games_season ON games(season);
CREATE INDEX idx_games_home_team ON games(home_team_id);
CREATE INDEX idx_games_away_team ON games(away_team_id);
CREATE INDEX idx_games_status ON games(status);
CREATE INDEX idx_games_conference ON games(is_conference_game);

CREATE INDEX idx_spreads_game ON spreads(game_id);
CREATE INDEX idx_spreads_captured ON spreads(captured_at);
CREATE INDEX idx_spreads_closing ON spreads(is_closing_line) WHERE is_closing_line = TRUE;

CREATE INDEX idx_rankings_team_season ON rankings(team_id, season);
CREATE INDEX idx_rankings_season_week ON rankings(season, week);
CREATE INDEX idx_rankings_rank ON rankings(rank) WHERE rank IS NOT NULL;

CREATE INDEX idx_predictions_game ON predictions(game_id);
CREATE INDEX idx_predictions_confidence ON predictions(confidence_tier);
CREATE INDEX idx_predictions_date ON predictions(created_at);

CREATE INDEX idx_ai_analysis_game ON ai_analysis(game_id);
CREATE INDEX idx_ai_analysis_provider ON ai_analysis(ai_provider);

CREATE INDEX idx_bet_results_game ON bet_results(game_id);
CREATE INDEX idx_bet_results_result ON bet_results(result);
CREATE INDEX idx_bet_results_pending ON bet_results(result) WHERE result = 'pending';

-- ============================================
-- ROW LEVEL SECURITY (Optional - for multi-user)
-- ============================================
-- Uncomment if you want to add auth later
-- ALTER TABLE games ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE bet_results ENABLE ROW LEVEL SECURITY;

-- ============================================
-- FUNCTIONS
-- ============================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
CREATE TRIGGER teams_updated_at
  BEFORE UPDATE ON teams
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER games_updated_at
  BEFORE UPDATE ON games
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Function to calculate game result for spread bets
CREATE OR REPLACE FUNCTION calculate_spread_result(
  p_home_score INTEGER,
  p_away_score INTEGER,
  p_spread DECIMAL,
  p_side TEXT
) RETURNS TEXT AS $$
DECLARE
  v_margin INTEGER;
  v_covered BOOLEAN;
BEGIN
  v_margin := p_home_score - p_away_score;

  IF p_side = 'home' THEN
    -- Home team covers if they win by more than the spread (or lose by less if underdog)
    v_covered := v_margin > (-1 * p_spread);
    IF v_margin = (-1 * p_spread) THEN
      RETURN 'push';
    END IF;
  ELSE
    -- Away team covers
    v_covered := (-1 * v_margin) > (-1 * (-1 * p_spread));
    IF v_margin = (-1 * p_spread) THEN
      RETURN 'push';
    END IF;
  END IF;

  IF v_covered THEN
    RETURN 'win';
  ELSE
    RETURN 'loss';
  END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VIEWS
-- ============================================

-- Today's games with spreads and predictions
CREATE OR REPLACE VIEW today_games AS
SELECT
  g.id,
  g.date,
  g.tip_time,
  ht.name as home_team,
  ht.conference as home_conference,
  at.name as away_team,
  at.conference as away_conference,
  g.is_conference_game,
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
  SELECT * FROM spreads
  WHERE game_id = g.id
  ORDER BY captured_at DESC
  LIMIT 1
) s ON TRUE
LEFT JOIN rankings hr ON hr.team_id = g.home_team_id
  AND hr.season = g.season
  AND hr.week = (SELECT MAX(week) FROM rankings WHERE season = g.season)
LEFT JOIN rankings ar ON ar.team_id = g.away_team_id
  AND ar.season = g.season
  AND ar.week = (SELECT MAX(week) FROM rankings WHERE season = g.season)
LEFT JOIN LATERAL (
  SELECT * FROM predictions
  WHERE game_id = g.id
  ORDER BY created_at DESC
  LIMIT 1
) p ON TRUE
WHERE g.date = CURRENT_DATE
ORDER BY g.tip_time, g.id;

-- Season performance summary
CREATE OR REPLACE VIEW season_performance AS
SELECT
  season,
  COUNT(*) as total_bets,
  SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
  SUM(CASE WHEN result = 'push' THEN 1 ELSE 0 END) as pushes,
  ROUND(
    100.0 * SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) /
    NULLIF(SUM(CASE WHEN result IN ('win', 'loss') THEN 1 ELSE 0 END), 0),
    1
  ) as win_pct,
  SUM(units_wagered) as units_wagered,
  SUM(units_won) as units_won,
  ROUND(
    100.0 * SUM(units_won) / NULLIF(SUM(units_wagered), 0),
    2
  ) as roi_pct
FROM bet_results br
JOIN games g ON br.game_id = g.id
WHERE br.result IN ('win', 'loss', 'push')
GROUP BY season
ORDER BY season DESC;
