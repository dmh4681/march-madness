# CLAUDE.md - Project Context for Claude Code

## Project Overview

**Conference Contrarian** is a full-stack college basketball betting analysis application. It uses AI (Claude) to analyze games and provide betting recommendations, with a focus on finding edges in the NCAA basketball betting market.

## Tech Stack

| Layer | Technology | Deployment |
|-------|------------|------------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS | Vercel |
| Backend API | FastAPI, Python 3.11 | Railway |
| Database | PostgreSQL via Supabase | Supabase |
| AI Analysis | Claude API (Anthropic) | Via Railway backend |
| Data Sources | The Odds API, CBBpy, KenPom | APIs |
| Advanced Analytics | KenPom (kenpompy) | Via Railway backend |

## Project Structure

```
march-madness/
├── frontend/                    # Next.js application
│   ├── src/
│   │   ├── app/                # App Router pages
│   │   │   ├── page.tsx        # Dashboard (today's games)
│   │   │   ├── games/
│   │   │   │   ├── page.tsx    # All upcoming games
│   │   │   │   └── [id]/page.tsx  # Game detail with AI analysis
│   │   │   ├── march-madness/  # Tournament bracket view
│   │   │   └── performance/    # Stats and ROI tracking
│   │   ├── components/         # React components
│   │   │   ├── GameCard.tsx
│   │   │   ├── ConfidenceBadge.tsx
│   │   │   ├── PicksList.tsx
│   │   │   ├── AIAnalysis.tsx
│   │   │   └── AIAnalysisButton.tsx  # Triggers Claude analysis
│   │   └── lib/
│   │       ├── supabase.ts     # Supabase client with fallback
│   │       ├── types.ts        # TypeScript interfaces
│   │       └── api.ts          # Formatting utilities
│   └── .env.local              # Environment variables
│
├── backend/
│   ├── api/
│   │   ├── main.py             # FastAPI application
│   │   ├── supabase_client.py  # Database operations
│   │   └── ai_service.py       # Claude/Grok integration
│   ├── data_collection/
│   │   ├── daily_refresh.py    # Daily data pipeline
│   │   ├── kenpom_scraper.py   # KenPom advanced analytics
│   │   ├── migrate_to_supabase.py  # Data migration
│   │   ├── scraper.py          # CBBpy data collection
│   │   └── rankings.py         # AP rankings scraper
│   ├── models/
│   │   └── baseline.py         # ML prediction models
│   └── analysis/
│       └── validate_edge.py    # Edge validation scripts
│
├── supabase/
│   └── migrations/             # SQL schema files
│       ├── 20250118000000_initial_schema.sql
│       ├── 20250118000001_today_games_view.sql
│       └── 20250119000000_kenpom_ratings.sql
│
├── .github/
│   └── workflows/
│       └── daily-refresh.yml   # GitHub Actions cron job
│
├── Procfile                    # Railway deployment
├── railway.json                # Railway config
├── runtime.txt                 # Python version
├── requirements.txt            # Python dependencies
└── PROJECT_JOURNEY.md          # Full build documentation
```

## Key API Endpoints (Railway Backend)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with API status |
| `/today` | GET | Today's games with spreads and predictions |
| `/games` | GET | Upcoming games (7 days) |
| `/games/{id}` | GET | Single game details |
| `/predict` | POST | Get prediction for a game |
| `/ai-analysis` | POST | Run Claude AI analysis on a game |
| `/refresh` | POST | Trigger daily data refresh |
| `/stats` | GET | Season performance statistics |
| `/rankings` | GET | Current AP rankings |

## Database Schema (Supabase)

**Core Tables:**
- `teams` - 416 NCAA teams with conferences
- `games` - 6,400+ games (2020-2025)
- `spreads` - Betting lines from The Odds API
- `rankings` - AP poll rankings by week
- `predictions` - Model predictions per game
- `ai_analysis` - Claude/Grok analysis results
- `bet_results` - Tracking actual bet outcomes
- `kenpom_ratings` - KenPom advanced analytics (AdjO, AdjD, tempo, SOS, etc.)

**Views:**
- `today_games` - Today's games with all joined data
- `upcoming_games` - Next 7 days of games
- `latest_kenpom_ratings` - Most recent KenPom data per team

## Environment Variables

### Frontend (Vercel)
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=https://web-production-e5efb.up.railway.app
```

**IMPORTANT:** `NEXT_PUBLIC_API_URL` must include `https://` - without it, fetch requests will fail with 405 errors.

### Backend (Railway)
```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
ANTHROPIC_API_KEY=
GROK_API_KEY= (optional)
ODDS_API_KEY=
REFRESH_API_KEY= (optional, for cron auth)
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app

# KenPom Integration (requires subscription)
KENPOM_EMAIL=
KENPOM_PASSWORD=
```

## Development Commands

```bash
# Frontend
cd frontend
npm install
npm run dev          # Start dev server on localhost:3000
npm run build        # Production build

# Backend (local)
cd backend
pip install -r ../requirements.txt
uvicorn backend.api.main:app --reload  # Start on localhost:8000

# Run data migration
python -m backend.data_collection.migrate_to_supabase

# Trigger daily refresh
python -m backend.data_collection.daily_refresh
```

## Data Flow

1. **Daily at 6 AM EST** - GitHub Actions triggers `/refresh`
2. **Refresh Pipeline:**
   - Fetches spreads from The Odds API
   - Refreshes KenPom advanced analytics (if credentials configured)
   - Creates/updates games in Supabase
   - Runs predictions on upcoming games
   - Runs Claude AI analysis on today's games (includes KenPom data)
3. **Frontend** reads from Supabase views
4. **Users** can trigger AI analysis on-demand via button

## AI Analysis

The AI service (`backend/api/ai_service.py`) uses Claude to analyze games:

- Builds context with team rankings, spread, venue, conference
- **Includes KenPom data when available:** AdjO, AdjD, efficiency margin, tempo, SOS, luck
- Sends structured prompt asking for betting recommendation
- When KenPom data is present, prompts Claude to use efficiency differentials for spread predictions
- Parses JSON response with: recommended_bet, confidence_score, key_factors, reasoning
- Stores analysis in `ai_analysis` table

### KenPom Integration

The KenPom scraper (`backend/data_collection/kenpom_scraper.py`) uses the `kenpompy` library:

- Requires KenPom subscription credentials (KENPOM_EMAIL, KENPOM_PASSWORD)
- Fetches all 350+ team ratings including:
  - Adjusted Offensive Efficiency (AdjO)
  - Adjusted Defensive Efficiency (AdjD)
  - Adjusted Efficiency Margin (AdjEM = AdjO - AdjD)
  - Adjusted Tempo
  - Strength of Schedule
  - Luck factor
- Stores in `kenpom_ratings` table with daily snapshots
- AI analysis prompt is enhanced when KenPom data is available

## Current Status

**Working:**
- Dashboard with table view of today's games and AI-powered picks
- Game detail pages with full AI analysis (Claude)
- "Run AI Analysis" button on game pages
- Daily refresh pipeline (GitHub Actions)
- KenPom advanced analytics integration
- AI analysis enhanced with KenPom data (AdjO, AdjD, tempo, SOS, luck)
- SQL views prioritize AI analysis over baseline predictions
- Spread-based probability heuristics for baseline model
- Compact table view with games showing Pick, Confidence, and Edge

**In Progress:**
- Performance tracking page (placeholder, needs real data)
- March Madness bracket page (placeholder, ready for Selection Sunday)

**Pending/Future:**
- Grok AI analysis (secondary AI for comparison) - see implementation plan
- Haslametrics integration (requires Selenium scraping) - see implementation plan
- User authentication (Supabase Auth)
- Payment/subscription (Stripe)
- Custom domain
- Bet result tracking
- Email notifications for high-confidence picks
- Mobile app

## Common Tasks

### Add a new page
1. Create `frontend/src/app/[route]/page.tsx`
2. Use server components for data fetching
3. Client components for interactivity (add 'use client')

### Add a new API endpoint
1. Add route in `backend/api/main.py`
2. Add any database functions to `supabase_client.py`
3. Push to trigger Railway deploy

### Update database schema
1. Create new migration in `supabase/migrations/`
2. Run SQL in Supabase dashboard
3. Update TypeScript types in `frontend/src/lib/types.ts`

## Notes

- Frontend shows empty states when Supabase isn't configured (no demo data)
- The Odds API free tier: 500 requests/month
- Railway auto-deploys on git push
- Vercel auto-deploys on git push
- KenPom requires paid subscription - scraper uses browser automation via Selenium
- AI analysis is stored in `ai_analysis` table with `ai_provider` field to distinguish Claude vs Grok

## Implementation Plan: Grok + Haslametrics

### Phase 1: Grok AI Integration

**Goal:** Add Grok as a secondary AI provider to compare analysis with Claude.

**Backend Changes (`backend/api/ai_service.py`):**
```python
# 1. Add Grok API client (uses OpenAI-compatible API)
import openai

class AIAnalyzer:
    def __init__(self):
        self.claude_client = anthropic.Anthropic()
        self.grok_client = openai.OpenAI(
            api_key=os.getenv("GROK_API_KEY"),
            base_url="https://api.x.ai/v1"  # Grok API endpoint
        )

    def _grok_analyze(self, prompt: str) -> dict:
        response = self.grok_client.chat.completions.create(
            model="grok-beta",  # or latest Grok model
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return self._parse_response(response.choices[0].message.content)
```

**API Endpoint Updates (`backend/api/main.py`):**
- Add `provider` parameter to `/ai-analysis` endpoint (default: "claude")
- Add `/ai-analysis/compare` endpoint that runs both Claude and Grok

**Frontend Changes:**
- Update `AIAnalysisButton.tsx` to allow provider selection
- Update `AIAnalysis.tsx` to show side-by-side comparison when both analyses exist
- Add "Run Grok Analysis" option on game detail page

**Database:**
- `ai_analysis` table already has `ai_provider` column - no schema changes needed

**Environment Variables:**
- Add `GROK_API_KEY` to Railway

**Estimated Work:**
- Backend: Update ai_service.py with Grok client
- Backend: Add provider param to endpoint
- Frontend: Add provider toggle/button
- Frontend: Side-by-side analysis display
- Deploy and test

---

### Phase 2: Haslametrics Integration

**Goal:** Add Haslametrics advanced metrics alongside KenPom.

**Challenge:** No public API - requires Selenium scraping like KenPom.

**Backend Changes (`backend/data_collection/haslametrics_scraper.py`):**
```python
# New file: Haslametrics scraper
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

def scrape_haslametrics(season: int = 2025) -> list[dict]:
    """
    Scrapes Haslametrics ratings.
    URL: https://haslametrics.com/ratings.php

    Key metrics to capture:
    - Team ranking
    - Predictive rating
    - True tempo
    - Offensive efficiency
    - Defensive efficiency
    - Recent form rating
    - Strength of schedule
    """
    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://haslametrics.com/ratings.php")

    # Wait for table to load
    time.sleep(2)

    # Parse ratings table
    rows = driver.find_elements(By.CSS_SELECTOR, "table.ratings tbody tr")
    ratings = []
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        ratings.append({
            "rank": int(cols[0].text),
            "team": cols[1].text,
            "predictive_rating": float(cols[2].text),
            # ... more fields
        })

    driver.quit()
    return ratings
```

**Database Schema:**
```sql
-- New migration: supabase/migrations/20250121000000_haslametrics_ratings.sql
CREATE TABLE haslametrics_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id),
    season INTEGER NOT NULL,
    rank INTEGER,
    predictive_rating DECIMAL(6,2),
    true_tempo DECIMAL(4,1),
    offensive_efficiency DECIMAL(5,1),
    defensive_efficiency DECIMAL(5,1),
    recent_form DECIMAL(4,2),
    sos_rank INTEGER,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    captured_date DATE DEFAULT CURRENT_DATE,
    UNIQUE(team_id, season, captured_date)
);

CREATE INDEX idx_haslametrics_team_season ON haslametrics_ratings(team_id, season);
```

**AI Analysis Enhancement:**
- Update `build_analysis_prompt()` to include Haslametrics when available
- Add predictive rating differential to prompt
- Include recent form in context

**Frontend Changes:**
- Add Haslametrics panel to game detail page (similar to KenPom panel)
- Show predictive rating comparison

**Daily Refresh:**
- Add `refresh_haslametrics()` to daily pipeline
- Run after KenPom refresh (both use Selenium)

**Estimated Work:**
1. Create Selenium scraper for Haslametrics
2. Create database migration
3. Update TypeScript types
4. Update AI prompt with Haslametrics data
5. Add Haslametrics panel to game detail page
6. Add to daily refresh pipeline
7. Test and deploy

---

### Implementation Order

1. **Grok (simpler, faster win):**
   - Has official API (OpenAI-compatible)
   - Database already supports multiple providers
   - Can be deployed incrementally

2. **Haslametrics (more complex):**
   - Requires Selenium scraping
   - New database table needed
   - More testing required
   - Can run in parallel with KenPom scraper

### Prerequisites

- Grok API key (from x.ai)
- Haslametrics is free (no login required)
- Chrome/Chromium for Selenium on Railway

## Troubleshooting

### 405 Method Not Allowed on AI Analysis
- Check that `NEXT_PUBLIC_API_URL` in Vercel includes `https://`
- Check that `ALLOWED_ORIGINS` in Railway includes your exact Vercel URL

### KenPom data all NULL
- Ensure using `get_pomeroy_ratings()` not `get_efficiency()` in kenpom_scraper.py
- Check Railway logs for actual column names returned by kenpompy

### React Hydration Error #418
- Usually caused by `new Date()` in server components (different on server vs client)
- Use static dates or move date logic to client components
