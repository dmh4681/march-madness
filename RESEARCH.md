# Conference Contrarian - Research Findings

## Executive Summary

This document catalogs useful repositories, data sources, and code patterns discovered during research for the Conference Contrarian betting edge analyzer.

---

## Priority Data Collection Libraries

### 1. CBBpy (RECOMMENDED - Primary Scraper)
**Repo:** [dcstats/CBBpy](https://github.com/dcstats/CBBpy)
**PyPI:** `pip install cbbpy`

**Why Use:**
- Active maintenance (last updated Jan 2025)
- Comprehensive ESPN data: game info, boxscores, play-by-play, schedules
- Supports both men's and women's basketball
- Returns clean pandas DataFrames
- Includes team rankings at time of game

**Key Functions:**
```python
import cbbpy.mens_scraper as s

# Get game metadata (includes rankings, scores, referees)
s.get_game_info('401522202')

# Get boxscores
s.get_game_boxscore('401528028')

# Get schedules by team or conference
s.get_team_schedule('davidson', 2022)
s.get_conference_schedule('big-ten', 2023)

# Get all games on a date
s.get_games_range('11-30-2022', '12-10-2022')
```

**Steal:**
- Game info structure (includes AP rankings)
- Conference schedule fetching
- Date range querying pattern

---

### 2. kenpompy (KenPom Scraper - Requires Subscription)
**Repo:** [j-andrews7/kenpompy](https://github.com/j-andrews7/kenpompy)
**PyPI:** `pip install kenpompy`
**Docs:** [kenpompy.readthedocs.io](https://kenpompy.readthedocs.io/en/latest/)

**Why Use:**
- Access to KenPom efficiency metrics (AdjO, AdjD, AdjEM)
- Historical season summaries
- Conference ratings

**Requirements:**
- KenPom subscription (~$20/year)
- Python >= 3.9

**Key Functions:**
```python
from kenpompy.misc import get_pomeroy_ratings
from kenpompy.summary import get_efficiency

# Get team efficiency ratings
ratings = get_pomeroy_ratings(browser, season=2023)

# Get efficiency stats
efficiency = get_efficiency(browser, season=2023)
```

**Decision:** Skip for V1 (requires subscription), add in V2 for advanced features

---

### 3. NCAA API (Free Real-Time Data)
**Repo:** [henrygd/ncaa-api](https://github.com/henrygd/ncaa-api)

**Why Use:**
- Free, real-time data from NCAA.com
- AP rankings endpoint
- Game scores and schedules
- No authentication required

**Rate Limits:** 5 requests/second/IP

**Key Endpoints:**
```
GET /rankings/basketball-men/d1/associated-press  # AP Top 25
GET /scoreboard/basketball-men/d1/{year}/{week}   # Games
GET /game/{game_id}/boxscore                       # Game details
GET /schedule/basketball-men/d1/{year}/{month}    # Monthly schedule
```

**Steal:**
- AP rankings fetching
- Schedule structure

---

## Historical Data Sources

### Sports-Reference (College Basketball Reference)
**URL:** [sports-reference.com/cbb](https://www.sports-reference.com/cbb)

**Available Data:**
- Game logs back to 1950s
- Team stats and advanced metrics
- Schedule and results
- Conference affiliations

**Scraping Notes:**
- 30-second delay between requests recommended
- Use BeautifulSoup + requests
- Existing scraper: [ryansloan/NCAAStatScraper](https://github.com/ryansloan/NCAAStatScraper)

---

### College Poll Archive (AP Poll Historical)
**URL:** [collegepollarchive.com](https://www.collegepollarchive.com/basketball/men/index.cfm)

**Available Data:**
- AP Poll rankings 1949-present
- Weekly polls with votes and points
- Preseason and final polls
- #1 vs #2 matchup history

**Scraping Strategy:**
- Navigate by season: `/basketball/men/ap/seasons/byYear-{year}.cfm`
- Each week's poll available
- Need to map poll week to actual dates

---

### The Odds API (Historical Spreads)
**URL:** [the-odds-api.com](https://the-odds-api.com/sports-odds-data/ncaa-basketball-odds.html)

**Available Data:**
- NCAA basketball odds from late 2020
- Spreads, moneylines, totals
- Multiple sportsbooks (FanDuel, DraftKings, BetMGM, etc.)

**API Example:**
```
GET https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds
?regions=us
&markets=spreads,h2h,totals
&oddsFormat=american
&apiKey={KEY}
```

**Free Tier:** Limited requests, but sufficient for historical lookup
**Limitation:** Only data from late 2020

---

## Prediction Model Repositories

### 1. bszek213/cbb_machine_learning (HIGH ACCURACY)
**Repo:** [bszek213/cbb_machine_learning](https://github.com/bszek213/cbb_machine_learning)

**Results:**
- XGBoost: 96.89% accuracy
- Neural Network (Keras): 97.60% accuracy
- Data: 2010-2024, 27,973 samples, 55 features

**Steal:**
- Feature engineering (correlation filtering at 0.9 threshold)
- XGBoost hyperparameters (max_depth: 2, n_estimators: 200, learning_rate: 0.1)
- Web scraper pattern (`cbb_web_scraper.py`)

**Note:** High accuracy likely overfitted - test on out-of-sample data

---

### 2. adeshpande3/March-Madness-ML
**Repo:** [adeshpande3/March-Madness-ML](https://github.com/adeshpande3/March-Madness-ML)

**Structure:**
```
Data/               # CSVs with team stats, game results
DataPreprocessing.py  # Feature engineering
MarchMadness.py       # ML models and predictions
```

**Data Sources:**
- Kaggle (game results since 1985)
- Sports Reference (advanced ratings)

**Steal:**
- Data preprocessing pipeline
- Training matrix structure (xTrain, yTrain)

---

### 3. NBA-Machine-Learning-Sports-Betting (BETTING FRAMEWORK)
**Repo:** [kyleskom/NBA-Machine-Learning-Sports-Betting](https://github.com/kyleskom/NBA-Machine-Learning-Sports-Betting)

**Structure:**
```
src/Process-Data/     # Data collection + feature engineering
src/Train-Models/     # Model training
Models/               # Saved model artifacts
Flask/                # Web interface
main.py               # Prediction orchestration
```

**Key Features:**
- Expected value calculation
- Kelly Criterion stake sizing (-kc flag)
- Multiple sportsbook support
- SQLite storage for odds

**Steal:**
- Betting framework architecture
- Kelly Criterion implementation
- EV calculation logic
- Sportsbook odds integration pattern

---

## Data Schema Design

Based on analysis of existing repos, here's the recommended schema:

### games table
```sql
CREATE TABLE games (
    game_id TEXT PRIMARY KEY,
    date DATE NOT NULL,
    season INTEGER NOT NULL,

    -- Teams
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_conference TEXT,
    away_conference TEXT,

    -- Rankings (NULL = unranked)
    home_ap_rank INTEGER,
    away_ap_rank INTEGER,

    -- Scores
    home_score INTEGER,
    away_score INTEGER,

    -- Betting
    spread REAL,           -- Positive = home is underdog
    spread_result TEXT,    -- 'home_cover', 'away_cover', 'push'
    over_under REAL,
    ou_result TEXT,        -- 'over', 'under', 'push'

    -- Derived
    same_conference BOOLEAN,
    ranked_vs_unranked BOOLEAN,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### ap_rankings table
```sql
CREATE TABLE ap_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    poll_date DATE NOT NULL,
    team TEXT NOT NULL,
    rank INTEGER NOT NULL,
    first_place_votes INTEGER,
    total_points INTEGER,

    UNIQUE(season, week, team)
);
```

### predictions table
```sql
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT REFERENCES games(game_id),
    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Model output
    model_version TEXT,
    predicted_cover_prob REAL,  -- P(underdog covers)
    confidence_tier TEXT,       -- 'high', 'medium', 'low'

    -- Bet recommendation
    recommended_bet TEXT,       -- 'underdog', 'favorite', 'pass'
    edge_pct REAL,             -- Expected edge over market
    kelly_fraction REAL,       -- Recommended bet size

    -- Actual result (filled after game)
    actual_result TEXT,        -- 'win', 'loss', 'push'
    profit_loss REAL
);
```

---

## Code Patterns to Steal

### 1. Rate-Limited Scraper (from NCAAStatScraper)
```python
import time
import requests
from bs4 import BeautifulSoup

class RateLimitedScraper:
    def __init__(self, delay=30):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; ResearchBot/1.0)'
        })

    def fetch(self, url):
        response = self.session.get(url)
        time.sleep(self.delay)
        return BeautifulSoup(response.text, 'lxml')
```

### 2. Expected Value Calculation (from NBA-ML-Betting)
```python
def calculate_ev(win_prob, odds):
    """
    Calculate expected value for a bet

    Args:
        win_prob: Model's probability of winning
        odds: American odds (e.g., -110, +150)

    Returns:
        Expected value as decimal (-0.05 = -5% EV)
    """
    if odds < 0:
        decimal_odds = 1 + (100 / abs(odds))
    else:
        decimal_odds = 1 + (odds / 100)

    ev = (win_prob * (decimal_odds - 1)) - (1 - win_prob)
    return ev
```

### 3. Kelly Criterion (from NBA-ML-Betting)
```python
def kelly_criterion(win_prob, odds):
    """
    Calculate optimal bet size as fraction of bankroll

    Args:
        win_prob: Model's probability of winning
        odds: American odds

    Returns:
        Fraction of bankroll to bet (0.05 = 5%)
    """
    if odds < 0:
        b = 100 / abs(odds)
    else:
        b = odds / 100

    q = 1 - win_prob
    kelly = (win_prob * b - q) / b

    # Never bet more than 25% (quarter Kelly is common)
    return max(0, min(kelly * 0.25, 0.25))
```

---

## Implementation Priority

### Phase 1: Data Collection (Week 1)
1. Install CBBpy for game data
2. Build AP Poll scraper from College Poll Archive
3. Set up SQLite database with schema above
4. Collect 2014-2024 game data

### Phase 2: Edge Validation (Week 2)
1. Filter for same-conference, ranked-vs-unranked games
2. Run statistical tests (binomial, chi-square)
3. Document results in RESULTS.md
4. **DECISION POINT:** Continue or pivot

### Phase 3: Modeling (Week 3, if edge validates)
1. Feature engineering (steal from bszek213)
2. Train XGBoost baseline
3. Implement backtesting framework
4. Add Kelly Criterion sizing

### Phase 4: Production (Week 4)
1. FastAPI backend
2. Daily data refresh script
3. Prediction logging
4. Simple frontend dashboard

---

## Useful Links

- [CBBpy GitHub](https://github.com/dcstats/CBBpy)
- [kenpompy Documentation](https://kenpompy.readthedocs.io/)
- [NCAA API](https://github.com/henrygd/ncaa-api)
- [College Poll Archive](https://www.collegepollarchive.com/)
- [The Odds API](https://the-odds-api.com/)
- [Sports Reference CBB](https://www.sports-reference.com/cbb/)
- [NBA Betting ML (architecture reference)](https://github.com/kyleskom/NBA-Machine-Learning-Sports-Betting)
- [CBB ML High Accuracy Model](https://github.com/bszek213/cbb_machine_learning)
