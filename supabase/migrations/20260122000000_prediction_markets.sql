-- Prediction Market Integration
-- Stores Polymarket and Kalshi prediction market data for college basketball

-- Prediction market data storage
CREATE TABLE IF NOT EXISTS prediction_markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source identification
    source VARCHAR(20) NOT NULL,           -- 'polymarket' | 'kalshi'
    market_id VARCHAR(100) NOT NULL,       -- External market ID

    -- Market details
    title VARCHAR(500) NOT NULL,
    description TEXT,
    market_type VARCHAR(50) NOT NULL,      -- 'futures' | 'game' | 'prop'

    -- Outcomes (for multi-outcome markets)
    outcomes JSONB NOT NULL DEFAULT '[]',  -- [{name, price, volume}]

    -- For game-specific markets
    game_id UUID REFERENCES games(id),
    home_team_id UUID REFERENCES teams(id),
    away_team_id UUID REFERENCES teams(id),

    -- For futures markets
    team_id UUID REFERENCES teams(id),     -- Tournament winner markets
    tournament VARCHAR(50),                -- 'march_madness' | 'big_ten_tourney' etc

    -- Market state
    status VARCHAR(20) DEFAULT 'open',     -- open | closed | resolved
    volume DECIMAL(15,2),
    liquidity DECIMAL(15,2),

    -- Timestamps
    end_date TIMESTAMPTZ,
    captured_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(source, market_id)
);

-- Price history for tracking movement
CREATE TABLE IF NOT EXISTS prediction_market_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID REFERENCES prediction_markets(id) ON DELETE CASCADE,

    -- Price snapshot
    outcome_name VARCHAR(200),
    price DECIMAL(5,4),                    -- 0.0000 to 1.0000
    volume DECIMAL(15,2),

    captured_at TIMESTAMPTZ DEFAULT NOW()
);

-- Arbitrage opportunities detected
CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Market references
    prediction_market_id UUID REFERENCES prediction_markets(id),
    game_id UUID REFERENCES games(id),

    -- Opportunity details
    bet_type VARCHAR(50),                  -- 'home_ml' | 'away_ml' | 'home_spread' etc

    -- Price comparison
    sportsbook_implied_prob DECIMAL(5,4),
    prediction_market_prob DECIMAL(5,4),
    delta DECIMAL(6,3),                    -- Percentage difference

    -- Edge classification
    edge_direction VARCHAR(20),            -- 'prediction_higher' | 'sportsbook_higher'
    is_actionable BOOLEAN DEFAULT false,   -- Delta >= threshold

    captured_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_pm_source ON prediction_markets(source);
CREATE INDEX IF NOT EXISTS idx_pm_game ON prediction_markets(game_id);
CREATE INDEX IF NOT EXISTS idx_pm_team ON prediction_markets(team_id);
CREATE INDEX IF NOT EXISTS idx_pm_type ON prediction_markets(market_type);
CREATE INDEX IF NOT EXISTS idx_pm_status ON prediction_markets(status);
CREATE INDEX IF NOT EXISTS idx_pm_captured ON prediction_markets(captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_pmp_market ON prediction_market_prices(market_id, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_arb_game ON arbitrage_opportunities(game_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_arb_actionable ON arbitrage_opportunities(is_actionable, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_arb_pm ON arbitrage_opportunities(prediction_market_id);

-- Grant access to authenticated users and anon
GRANT SELECT ON prediction_markets TO authenticated, anon;
GRANT SELECT ON prediction_market_prices TO authenticated, anon;
GRANT SELECT ON arbitrage_opportunities TO authenticated, anon;

-- View for latest prediction market data per game
CREATE OR REPLACE VIEW game_prediction_markets AS
SELECT
    pm.id,
    pm.source,
    pm.market_id,
    pm.title,
    pm.market_type,
    pm.outcomes,
    pm.game_id,
    pm.status,
    pm.volume,
    pm.captured_at,
    g.date as game_date,
    g.home_team_id,
    g.away_team_id
FROM prediction_markets pm
JOIN games g ON pm.game_id = g.id
WHERE pm.status = 'open'
ORDER BY pm.captured_at DESC;

GRANT SELECT ON game_prediction_markets TO authenticated, anon;

-- View for actionable arbitrage opportunities
CREATE OR REPLACE VIEW actionable_arbitrage AS
SELECT
    ao.id,
    ao.game_id,
    ao.prediction_market_id,
    ao.bet_type,
    ao.sportsbook_implied_prob,
    ao.prediction_market_prob,
    ao.delta,
    ao.edge_direction,
    ao.captured_at,
    pm.source as market_source,
    pm.title as market_title,
    g.date as game_date,
    ht.name as home_team,
    at.name as away_team
FROM arbitrage_opportunities ao
JOIN prediction_markets pm ON ao.prediction_market_id = pm.id
JOIN games g ON ao.game_id = g.id
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams at ON g.away_team_id = at.id
WHERE ao.is_actionable = true
  AND ao.captured_at > NOW() - INTERVAL '24 hours'
ORDER BY ao.delta DESC;

GRANT SELECT ON actionable_arbitrage TO authenticated, anon;

COMMENT ON TABLE prediction_markets IS 'Stores prediction market data from Polymarket and Kalshi for college basketball';
COMMENT ON TABLE prediction_market_prices IS 'Historical price snapshots for prediction market outcomes';
COMMENT ON TABLE arbitrage_opportunities IS 'Detected arbitrage opportunities between prediction markets and sportsbooks';
