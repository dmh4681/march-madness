# Prediction Market Integration Plan

## Overview

Integrate Polymarket and Kalshi prediction market data into the March Madness app to provide:
1. **AI Analysis Enhancement** - Give Claude/Grok additional market signals for better picks
2. **Arbitrage Detection** - Identify edges between prediction markets and sportsbooks

---

## Data Sources

### Polymarket (Gamma API)
- **Base URL**: `https://gamma-api.polymarket.com`
- **Authentication**: None required for public endpoints
- **Key Endpoints**:
  - `GET /markets` - List markets with filters
  - `GET /markets/{id}` - Single market details
- **Notes**: Uses numeric IDs, not hex condition IDs. Filter by `tag=college-basketball` or `tag=ncaa`

### Kalshi (Trade API v2)
- **Base URL**: `https://trading-api.kalshi.com/trade-api/v2`
- **Authentication**: RSA-PSS-SHA256 signed requests
- **Key Endpoints**:
  - `GET /markets` - List markets with cursor pagination
  - `GET /markets/{ticker}` - Single market by ticker
- **Notes**: Requires API key + private key for signing. College basketball markets under series like `NCAAM-*`

---

## Database Schema

### New Tables

```sql
-- supabase/migrations/20260122000000_prediction_markets.sql

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

-- Indexes
CREATE INDEX idx_pm_source ON prediction_markets(source);
CREATE INDEX idx_pm_game ON prediction_markets(game_id);
CREATE INDEX idx_pm_team ON prediction_markets(team_id);
CREATE INDEX idx_pm_type ON prediction_markets(market_type);
CREATE INDEX idx_pm_captured ON prediction_markets(captured_at DESC);

CREATE INDEX idx_pmp_market ON prediction_market_prices(market_id, captured_at DESC);

CREATE INDEX idx_arb_game ON arbitrage_opportunities(game_id, captured_at DESC);
CREATE INDEX idx_arb_actionable ON arbitrage_opportunities(is_actionable, captured_at DESC);

-- Grant access
GRANT SELECT ON prediction_markets TO authenticated, anon;
GRANT SELECT ON prediction_market_prices TO authenticated, anon;
GRANT SELECT ON arbitrage_opportunities TO authenticated, anon;
```

### Type Updates

```typescript
// frontend/src/lib/types.ts

export interface PredictionMarket {
  id: string;
  source: 'polymarket' | 'kalshi';
  market_id: string;
  title: string;
  description?: string;
  market_type: 'futures' | 'game' | 'prop';
  outcomes: PredictionOutcome[];
  game_id?: string;
  team_id?: string;
  status: 'open' | 'closed' | 'resolved';
  volume?: number;
  captured_at: string;
}

export interface PredictionOutcome {
  name: string;
  price: number;     // 0-1 probability
  volume?: number;
}

export interface ArbitrageOpportunity {
  id: string;
  game_id: string;
  bet_type: string;
  sportsbook_implied_prob: number;
  prediction_market_prob: number;
  delta: number;
  edge_direction: 'prediction_higher' | 'sportsbook_higher';
  is_actionable: boolean;
  captured_at: string;
}

// Extend TodayGame
export interface TodayGame {
  // ... existing fields ...

  // Prediction market data
  prediction_markets?: PredictionMarket[];
  arbitrage_opportunities?: ArbitrageOpportunity[];
  has_prediction_data?: boolean;
}
```

---

## Backend Implementation

### 1. Polymarket Client

```python
# backend/data_collection/polymarket_client.py

"""
Polymarket API client for college basketball markets.
"""

import httpx
from typing import Optional
from datetime import datetime

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"

class PolymarketClient:
    """Client for Polymarket Gamma API."""

    def __init__(self):
        self.client = httpx.AsyncClient(base_url=GAMMA_BASE_URL)

    async def get_college_basketball_markets(self) -> list[dict]:
        """Fetch all college basketball markets."""
        markets = []

        # Try multiple relevant tags
        tags = ["college-basketball", "ncaa", "march-madness", "ncaa-basketball"]

        for tag in tags:
            response = await self.client.get(
                "/markets",
                params={"tag": tag, "closed": "false", "limit": 100}
            )
            if response.status_code == 200:
                data = response.json()
                markets.extend(data if isinstance(data, list) else data.get("markets", []))

        # Deduplicate by market ID
        seen = set()
        unique_markets = []
        for m in markets:
            if m["id"] not in seen:
                seen.add(m["id"])
                unique_markets.append(m)

        return unique_markets

    async def get_market(self, market_id: str) -> Optional[dict]:
        """Fetch single market by ID."""
        response = await self.client.get(f"/markets/{market_id}")
        if response.status_code == 200:
            return response.json()
        return None

    def parse_market(self, raw: dict) -> dict:
        """Parse Polymarket response into standard format."""
        outcomes = []

        # Polymarket uses 'outcomes' array with prices
        for outcome in raw.get("outcomes", []):
            outcomes.append({
                "name": outcome.get("name") or outcome.get("outcome"),
                "price": float(outcome.get("price", 0)),
                "volume": float(outcome.get("volume", 0) or 0)
            })

        # Determine market type
        title_lower = raw.get("question", "").lower()
        market_type = "futures"
        if any(x in title_lower for x in ["vs", "versus", "beat", "win game"]):
            market_type = "game"
        elif any(x in title_lower for x in ["points", "score", "total"]):
            market_type = "prop"

        return {
            "source": "polymarket",
            "market_id": str(raw["id"]),
            "title": raw.get("question", raw.get("title", "")),
            "description": raw.get("description"),
            "market_type": market_type,
            "outcomes": outcomes,
            "status": "closed" if raw.get("closed") else "open",
            "volume": float(raw.get("volume", 0) or 0),
            "end_date": raw.get("endDate"),
        }

    async def close(self):
        await self.client.aclose()
```

### 2. Kalshi Client

```python
# backend/data_collection/kalshi_client.py

"""
Kalshi API client with RSA-PSS-SHA256 authentication.
Adapted from Dylan Heiney implementation.
"""

import os
import time
import base64
import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from typing import Optional

KALSHI_BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"

class KalshiClient:
    """Client for Kalshi Trade API v2."""

    def __init__(self):
        self.api_key = os.getenv("KALSHI_API_KEY")
        self.private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
        self._private_key = None
        self.client = httpx.AsyncClient(base_url=KALSHI_BASE_URL)

    @property
    def private_key(self):
        """Lazy load private key."""
        if self._private_key is None and self.private_key_path:
            with open(self.private_key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )
        return self._private_key

    def _sign_request(self, method: str, path: str, timestamp: str) -> str:
        """Generate RSA-PSS-SHA256 signature."""
        message = f"{timestamp}{method}{path}".encode()
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    def _get_headers(self, method: str, path: str) -> dict:
        """Build authenticated headers."""
        timestamp = str(int(time.time() * 1000))
        signature = self._sign_request(method, path, timestamp)

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

    async def get_college_basketball_markets(self) -> list[dict]:
        """Fetch NCAA basketball markets."""
        markets = []
        cursor = None

        # Search for relevant series
        series_prefixes = ["NCAAM", "NCAAB", "CBB", "MARCHMAD"]

        while True:
            path = "/markets"
            params = {"limit": 100, "status": "open"}
            if cursor:
                params["cursor"] = cursor

            headers = self._get_headers("GET", path)
            response = await self.client.get(path, headers=headers, params=params)

            if response.status_code != 200:
                break

            data = response.json()
            batch = data.get("markets", [])

            # Filter for college basketball
            for m in batch:
                ticker = m.get("ticker", "")
                title = m.get("title", "").lower()

                if any(ticker.startswith(p) for p in series_prefixes):
                    markets.append(m)
                elif any(x in title for x in ["ncaa", "college basketball", "march madness"]):
                    markets.append(m)

            cursor = data.get("cursor")
            if not cursor or not batch:
                break

        return markets

    async def get_market(self, ticker: str) -> Optional[dict]:
        """Fetch single market by ticker."""
        path = f"/markets/{ticker}"
        headers = self._get_headers("GET", path)
        response = await self.client.get(path, headers=headers)

        if response.status_code == 200:
            return response.json().get("market")
        return None

    def parse_market(self, raw: dict) -> dict:
        """Parse Kalshi response into standard format."""
        # Kalshi markets are binary (Yes/No)
        yes_price = raw.get("yes_ask", raw.get("last_price", 0.5))
        no_price = 1 - yes_price

        outcomes = [
            {"name": "Yes", "price": yes_price, "volume": raw.get("volume", 0)},
            {"name": "No", "price": no_price, "volume": raw.get("volume", 0)}
        ]

        # Determine market type from ticker/title
        ticker = raw.get("ticker", "")
        title = raw.get("title", "").lower()

        market_type = "futures"
        if "-VS-" in ticker or "vs" in title or "beat" in title:
            market_type = "game"
        elif any(x in title for x in ["points", "score", "total", "over", "under"]):
            market_type = "prop"

        return {
            "source": "kalshi",
            "market_id": raw.get("ticker"),
            "title": raw.get("title", ""),
            "description": raw.get("subtitle"),
            "market_type": market_type,
            "outcomes": outcomes,
            "status": raw.get("status", "open"),
            "volume": float(raw.get("volume", 0) or 0),
            "end_date": raw.get("close_time"),
        }

    async def close(self):
        await self.client.aclose()
```

### 3. Market Matcher Service

```python
# backend/data_collection/market_matcher.py

"""
Match prediction markets to games and teams in our database.
"""

import re
from difflib import SequenceMatcher
from typing import Optional, Tuple

# Team name variations for matching
TEAM_ALIASES = {
    "Duke": ["Duke Blue Devils", "Duke", "Blue Devils"],
    "North Carolina": ["UNC", "North Carolina", "Tar Heels", "North Carolina Tar Heels"],
    "Kentucky": ["Kentucky", "UK", "Wildcats", "Kentucky Wildcats"],
    "Kansas": ["Kansas", "KU", "Jayhawks", "Kansas Jayhawks"],
    "Gonzaga": ["Gonzaga", "Zags", "Bulldogs", "Gonzaga Bulldogs"],
    # Add more as needed
}

def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    # Remove common suffixes
    for suffix in ["university", "state", "college"]:
        name = name.replace(suffix, "").strip()
    return name

def match_team_name(market_name: str, db_teams: list[dict]) -> Optional[dict]:
    """Find best matching team from database."""
    market_normalized = normalize_team_name(market_name)

    best_match = None
    best_score = 0.0

    for team in db_teams:
        team_name = team["name"]
        team_normalized = normalize_team_name(team_name)

        # Direct match
        if market_normalized == team_normalized:
            return team

        # Partial match
        score = SequenceMatcher(None, market_normalized, team_normalized).ratio()

        # Check aliases
        for alias_key, aliases in TEAM_ALIASES.items():
            if any(a.lower() in market_normalized for a in aliases):
                if alias_key.lower() in team_normalized:
                    score = max(score, 0.9)

        if score > best_score and score > 0.6:
            best_score = score
            best_match = team

    return best_match

def extract_game_teams(market_title: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract team names from game market title."""
    # Common patterns: "Duke vs UNC", "Duke to beat UNC", "Will Duke beat UNC?"
    patterns = [
        r"(.+?)\s+(?:vs\.?|versus|to beat|beat)\s+(.+?)(?:\?|$)",
        r"Will (.+?) beat (.+?)\??",
        r"(.+?)\s+-\s+(.+?)\s+(?:game|match)",
    ]

    for pattern in patterns:
        match = re.search(pattern, market_title, re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()

    return None, None

async def match_market_to_game(market: dict, games: list[dict], teams: list[dict]) -> Optional[str]:
    """Match a game-type market to a game_id."""
    if market["market_type"] != "game":
        return None

    team1_name, team2_name = extract_game_teams(market["title"])
    if not team1_name or not team2_name:
        return None

    team1 = match_team_name(team1_name, teams)
    team2 = match_team_name(team2_name, teams)

    if not team1 or not team2:
        return None

    # Find game with these teams
    for game in games:
        game_teams = {game["home_team_id"], game["away_team_id"]}
        if team1["id"] in game_teams and team2["id"] in game_teams:
            return game["id"]

    return None

async def match_market_to_team(market: dict, teams: list[dict]) -> Optional[str]:
    """Match a futures market to a team_id."""
    if market["market_type"] != "futures":
        return None

    # Look for team name in outcomes or title
    for outcome in market.get("outcomes", []):
        team = match_team_name(outcome["name"], teams)
        if team:
            return team["id"]

    # Try title
    team = match_team_name(market["title"], teams)
    if team:
        return team["id"]

    return None
```

### 4. Arbitrage Detector

```python
# backend/data_collection/arbitrage_detector.py

"""
Detect arbitrage opportunities between prediction markets and sportsbooks.
"""

from typing import Optional
from decimal import Decimal

EDGE_THRESHOLD = 10.0  # Minimum delta % to flag as actionable

def american_odds_to_prob(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds is None:
        return 0.5
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)

def detect_arbitrage(
    game: dict,
    prediction_market: dict,
    bet_type: str
) -> Optional[dict]:
    """
    Compare prediction market price to sportsbook implied probability.

    Args:
        game: Game data with spreads
        prediction_market: Prediction market data
        bet_type: 'home_ml', 'away_ml', 'home_spread', 'away_spread'

    Returns:
        Arbitrage opportunity if edge detected, else None
    """
    # Get sportsbook implied probability
    if bet_type == "home_ml":
        sportsbook_prob = american_odds_to_prob(game.get("home_ml"))
    elif bet_type == "away_ml":
        sportsbook_prob = american_odds_to_prob(game.get("away_ml"))
    elif bet_type == "home_spread":
        # Spread bets typically -110 both sides = 52.38%
        sportsbook_prob = 0.5238
    elif bet_type == "away_spread":
        sportsbook_prob = 0.5238
    else:
        return None

    # Find matching outcome in prediction market
    pm_prob = None
    for outcome in prediction_market.get("outcomes", []):
        outcome_name = outcome["name"].lower()

        if bet_type in ["home_ml", "home_spread"]:
            if game["home_team"].lower() in outcome_name or outcome_name == "yes":
                pm_prob = outcome["price"]
                break
        elif bet_type in ["away_ml", "away_spread"]:
            if game["away_team"].lower() in outcome_name or outcome_name == "no":
                pm_prob = outcome["price"]
                break

    if pm_prob is None:
        return None

    # Calculate delta
    delta = (pm_prob - sportsbook_prob) * 100

    # Determine direction
    if delta > 0:
        edge_direction = "prediction_higher"
    else:
        edge_direction = "sportsbook_higher"

    return {
        "game_id": game["id"],
        "prediction_market_id": prediction_market["id"],
        "bet_type": bet_type,
        "sportsbook_implied_prob": round(sportsbook_prob, 4),
        "prediction_market_prob": round(pm_prob, 4),
        "delta": round(abs(delta), 3),
        "edge_direction": edge_direction,
        "is_actionable": abs(delta) >= EDGE_THRESHOLD
    }

async def scan_game_for_arbitrage(game: dict, markets: list[dict]) -> list[dict]:
    """Scan all prediction markets for a game and find arbitrage."""
    opportunities = []

    for market in markets:
        if market.get("game_id") != game["id"]:
            continue

        # Check each bet type
        for bet_type in ["home_ml", "away_ml"]:
            opp = detect_arbitrage(game, market, bet_type)
            if opp:
                opportunities.append(opp)

    return opportunities
```

### 5. Main Scraper Service

```python
# backend/data_collection/prediction_market_scraper.py

"""
Main service for scraping and processing prediction market data.
"""

import asyncio
from datetime import datetime
from .polymarket_client import PolymarketClient
from .kalshi_client import KalshiClient
from .market_matcher import match_market_to_game, match_market_to_team
from .arbitrage_detector import scan_game_for_arbitrage
from ..api.supabase_client import get_supabase

async def refresh_prediction_markets():
    """
    Fetch latest prediction market data from all sources.
    Match to games/teams and detect arbitrage.
    """
    supabase = get_supabase()

    # Get reference data
    games_resp = supabase.table("upcoming_games").select("*").execute()
    games = games_resp.data or []

    teams_resp = supabase.table("teams").select("id, name").execute()
    teams = teams_resp.data or []

    results = {
        "polymarket": {"fetched": 0, "matched": 0},
        "kalshi": {"fetched": 0, "matched": 0},
        "arbitrage": {"detected": 0, "actionable": 0}
    }

    # Fetch from Polymarket
    poly_client = PolymarketClient()
    try:
        poly_markets = await poly_client.get_college_basketball_markets()
        results["polymarket"]["fetched"] = len(poly_markets)

        for raw in poly_markets:
            market = poly_client.parse_market(raw)

            # Try to match to game or team
            game_id = await match_market_to_game(market, games, teams)
            team_id = await match_market_to_team(market, teams)

            if game_id or team_id:
                results["polymarket"]["matched"] += 1
                market["game_id"] = game_id
                market["team_id"] = team_id

                # Upsert to database
                supabase.table("prediction_markets").upsert(
                    market, on_conflict="source,market_id"
                ).execute()
    finally:
        await poly_client.close()

    # Fetch from Kalshi
    kalshi_client = KalshiClient()
    try:
        kalshi_markets = await kalshi_client.get_college_basketball_markets()
        results["kalshi"]["fetched"] = len(kalshi_markets)

        for raw in kalshi_markets:
            market = kalshi_client.parse_market(raw)

            game_id = await match_market_to_game(market, games, teams)
            team_id = await match_market_to_team(market, teams)

            if game_id or team_id:
                results["kalshi"]["matched"] += 1
                market["game_id"] = game_id
                market["team_id"] = team_id

                supabase.table("prediction_markets").upsert(
                    market, on_conflict="source,market_id"
                ).execute()
    finally:
        await kalshi_client.close()

    # Detect arbitrage for all games with prediction data
    markets_resp = supabase.table("prediction_markets").select("*").execute()
    all_markets = markets_resp.data or []

    for game in games:
        opportunities = await scan_game_for_arbitrage(game, all_markets)

        for opp in opportunities:
            results["arbitrage"]["detected"] += 1
            if opp["is_actionable"]:
                results["arbitrage"]["actionable"] += 1

            supabase.table("arbitrage_opportunities").insert(opp).execute()

    return results
```

### 6. Integration into Daily Refresh

```python
# Modify backend/data_collection/daily_refresh.py

def run_daily_refresh(force_regenerate_predictions=False):
    # ... existing steps ...

    # Step 5: Refresh prediction markets
    try:
        from .prediction_market_scraper import refresh_prediction_markets
        pm_results = asyncio.run(refresh_prediction_markets())
        results["prediction_markets"] = pm_results
        logger.info(
            f"Prediction Markets: Poly {pm_results['polymarket']['matched']}, "
            f"Kalshi {pm_results['kalshi']['matched']}, "
            f"Arbitrage {pm_results['arbitrage']['actionable']} actionable"
        )
    except Exception as e:
        logger.error(f"Prediction market refresh failed (non-fatal): {e}")
        results["prediction_markets"] = {"error": str(e)}

    # ... continue with existing steps ...
```

---

## AI Analysis Integration

### Update Game Context Builder

```python
# Modify backend/api/ai_service.py

def build_game_context(game_id: str) -> dict:
    # ... existing code ...

    # Add prediction market data
    pm_data = get_game_prediction_markets(game_id)
    arbitrage = get_game_arbitrage(game_id)

    context["prediction_markets"] = pm_data
    context["arbitrage_opportunities"] = arbitrage

    return context

def build_analysis_prompt(context: dict) -> str:
    # ... existing sections ...

    # Prediction Markets section
    pm_section = ""
    if context.get("prediction_markets"):
        pm_section = "\n## PREDICTION MARKET DATA\n"

        for pm in context["prediction_markets"]:
            pm_section += f"\n**{pm['source'].title()}**: {pm['title']}\n"
            for outcome in pm["outcomes"]:
                pm_section += f"  - {outcome['name']}: {outcome['price']*100:.1f}%\n"
            if pm.get("volume"):
                pm_section += f"  - Volume: ${pm['volume']:,.0f}\n"

    # Arbitrage section
    arb_section = ""
    if context.get("arbitrage_opportunities"):
        arb_section = "\n## ARBITRAGE SIGNALS\n"

        for arb in context["arbitrage_opportunities"]:
            direction = "higher" if arb["edge_direction"] == "prediction_higher" else "lower"
            arb_section += f"""
**{arb['bet_type'].replace('_', ' ').title()}**
- Sportsbook implied: {arb['sportsbook_implied_prob']*100:.1f}%
- Prediction market: {arb['prediction_market_prob']*100:.1f}%
- Delta: {arb['delta']:.1f}% ({direction} on prediction market)
- Actionable: {"YES" if arb['is_actionable'] else "No"}
"""

        arb_section += """
**Arbitrage Analysis Points:**
- Large deltas may indicate market inefficiency or information asymmetry
- Prediction markets often capture public sentiment differently than sportsbooks
- Consider volume/liquidity when assessing signal reliability
"""

    prompt = f"""...{kenpom_section}{haslametrics_section}{pm_section}{arb_section}..."""
```

---

## Frontend Updates (Minimal)

### 1. Add to Game Detail Page

```tsx
// Modify frontend/src/app/games/[id]/page.tsx

// In the game detail component, add prediction market section:
{game.prediction_markets && game.prediction_markets.length > 0 && (
  <div className="mt-4 p-4 bg-gray-800 rounded-lg">
    <h4 className="text-sm font-medium text-gray-400 mb-2">
      Prediction Markets
    </h4>
    <div className="space-y-2">
      {game.prediction_markets.map((pm) => (
        <div key={pm.id} className="flex items-center justify-between text-sm">
          <span className="text-gray-300">
            {pm.source === 'polymarket' ? '🔮' : '📊'} {pm.title}
          </span>
          <div className="flex gap-2">
            {pm.outcomes.slice(0, 2).map((o) => (
              <span
                key={o.name}
                className="px-2 py-0.5 bg-gray-700 rounded text-xs"
              >
                {o.name}: {(o.price * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  </div>
)}

{/* Arbitrage Alert */}
{game.arbitrage_opportunities?.some(a => a.is_actionable) && (
  <div className="mt-2 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
    <div className="flex items-center gap-2">
      <span className="text-yellow-400 text-sm font-medium">
        ⚡ Arbitrage Signal Detected
      </span>
    </div>
    <p className="text-xs text-yellow-400/80 mt-1">
      {game.arbitrage_opportunities.filter(a => a.is_actionable).length} opportunity(s)
      with ≥10% edge between prediction markets and sportsbooks
    </p>
  </div>
)}
```

### 2. Add Indicator to Games Table

```tsx
// Modify frontend/src/components/GamesTable.tsx

// Add column header
<th className="py-3 px-2 font-medium text-center">PM</th>

// Add cell
<td className="py-3 px-2 text-center">
  {game.has_prediction_data ? (
    <span
      className={`w-2 h-2 rounded-full inline-block ${
        game.arbitrage_opportunities?.some(a => a.is_actionable)
          ? 'bg-yellow-500'
          : 'bg-purple-500'
      }`}
      title={
        game.arbitrage_opportunities?.some(a => a.is_actionable)
          ? 'Arbitrage detected'
          : 'Prediction market data available'
      }
    />
  ) : (
    <span className="text-gray-600 text-xs">-</span>
  )}
</td>
```

### 3. Update Legend

```tsx
// Modify frontend/src/components/GamesSection.tsx

// Add to legend
<span className="flex items-center gap-1">
  <span className="w-2 h-2 rounded-full bg-purple-500" />
  Prediction Markets
</span>
<span className="flex items-center gap-1">
  <span className="w-2 h-2 rounded-full bg-yellow-500" />
  Arbitrage
</span>
```

---

## SQL View Updates

```sql
-- Update today_games and upcoming_games views to include prediction market flags

-- Add to SELECT clause:
(EXISTS (
    SELECT 1 FROM prediction_markets pm
    WHERE pm.game_id = g.id
)) as has_prediction_data,

(EXISTS (
    SELECT 1 FROM arbitrage_opportunities ao
    WHERE ao.game_id = g.id AND ao.is_actionable = true
    AND ao.captured_at > NOW() - INTERVAL '24 hours'
)) as has_arbitrage_signal
```

---

## Environment Variables

```bash
# Add to Railway / .env

# Kalshi API (required for Kalshi markets)
KALSHI_API_KEY=your_api_key
KALSHI_PRIVATE_KEY_PATH=/path/to/kalshi_private_key.pem

# Optional: Rate limiting
PM_REFRESH_INTERVAL_MINUTES=30
```

---

## Implementation Phases

### Phase 1: Database & Basic Scraping
1. Run database migration
2. Implement Polymarket client (no auth needed)
3. Test market fetching and storage
4. Add to daily refresh

### Phase 2: Kalshi Integration
1. Set up Kalshi API credentials
2. Implement RSA-PSS signing
3. Add Kalshi client
4. Test alongside Polymarket

### Phase 3: Matching & Arbitrage
1. Implement team/game matching logic
2. Build arbitrage detector
3. Test edge detection accuracy
4. Tune threshold parameters

### Phase 4: AI Integration
1. Add prediction data to game context
2. Update AI prompts
3. Test Claude/Grok analysis quality
4. Refine prompt formatting

### Phase 5: Frontend
1. Add prediction market indicators
2. Show arbitrage alerts
3. Update legends
4. Test UI/UX

---

## Files Summary

### New Files
- `backend/data_collection/polymarket_client.py`
- `backend/data_collection/kalshi_client.py`
- `backend/data_collection/market_matcher.py`
- `backend/data_collection/arbitrage_detector.py`
- `backend/data_collection/prediction_market_scraper.py`
- `supabase/migrations/20260122000000_prediction_markets.sql`

### Modified Files
- `backend/data_collection/daily_refresh.py` - Add PM refresh step
- `backend/api/ai_service.py` - Add PM context to prompts
- `backend/api/supabase_client.py` - Add PM query functions
- `frontend/src/lib/types.ts` - Add PM types
- `frontend/src/components/GamesTable.tsx` - Add PM column
- `frontend/src/components/GamesSection.tsx` - Update legend
- `frontend/src/app/games/[id]/page.tsx` - Show PM data

---

## Testing Checklist

- [ ] Polymarket API returns college basketball markets
- [ ] Kalshi authentication works (if credentials provided)
- [ ] Markets correctly match to games/teams
- [ ] Arbitrage detection calculates correct deltas
- [ ] Daily refresh includes PM step without errors
- [ ] AI prompts include PM data when available
- [ ] Frontend shows PM indicators
- [ ] Arbitrage alerts display correctly
