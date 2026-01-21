# CLAUDE.md - Project Context for Claude Code

## Project Overview

**Conference Contrarian** is a full-stack college basketball betting analysis application. It uses AI (Claude and Grok) to analyze games and provide betting recommendations, with a focus on finding edges in the NCAA basketball betting market using advanced analytics from KenPom and Haslametrics.

**Live Site:** https://confcontrarian.com

## Tech Stack

| Layer | Technology | Deployment |
|-------|------------|------------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS | Vercel |
| Backend API | FastAPI, Python 3.11 | Railway |
| Database | PostgreSQL via Supabase | Supabase |
| AI Analysis | Claude API (Anthropic), Grok API (xAI) | Via Railway backend |
| Data Sources | The Odds API, CBBpy | APIs |
| Advanced Analytics | KenPom (kenpompy), Haslametrics (XML) | Via Railway backend |

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
│   │   │   └── AIAnalysisButton.tsx  # Triggers Claude/Grok analysis
│   │   └── lib/
│   │       ├── supabase.ts     # Supabase client with fallback
│   │       ├── types.ts        # TypeScript interfaces
│   │       └── api.ts          # Formatting utilities
│   └── .env.local              # Environment variables
│
├── backend/
│   ├── api/
│   │   ├── main.py             # FastAPI application (with security middleware)
│   │   ├── supabase_client.py  # Database operations (with input validation)
│   │   └── ai_service.py       # Claude + Grok integration
│   ├── data_collection/
│   │   ├── daily_refresh.py    # Daily data pipeline
│   │   ├── kenpom_scraper.py   # KenPom advanced analytics
│   │   ├── haslametrics_scraper.py  # Haslametrics analytics (FREE)
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
│       ├── 20250119000000_kenpom_ratings.sql
│       └── 20250121000000_haslametrics_ratings.sql
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
| `/ai-analysis` | POST | Run Claude or Grok AI analysis (provider param) |
| `/refresh` | POST | Trigger full daily data refresh |
| `/refresh-haslametrics` | POST | Refresh only Haslametrics data (fast) |
| `/regenerate-predictions` | POST | Regenerate predictions only |
| `/stats` | GET | Season performance statistics |
| `/rankings` | GET | Current AP rankings |

## Database Schema (Supabase)

**Core Tables:**
- `teams` - 416 NCAA teams with conferences
- `games` - 6,400+ games (2020-2025)
- `spreads` - Betting lines from The Odds API (spread + moneyline)
- `rankings` - AP poll rankings by week
- `predictions` - Model predictions per game
- `ai_analysis` - Claude/Grok analysis results (ai_provider field distinguishes)
- `bet_results` - Tracking actual bet outcomes
- `kenpom_ratings` - KenPom advanced analytics (AdjO, AdjD, tempo, SOS, luck)
- `haslametrics_ratings` - Haslametrics analytics (All-Play %, momentum, efficiency)

**Views:**
- `today_games` - Today's games with all joined data
- `upcoming_games` - Next 7 days of games
- `latest_kenpom_ratings` - Most recent KenPom data per team
- `latest_haslametrics_ratings` - Most recent Haslametrics data per team

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
GROK_API_KEY=
ODDS_API_KEY=
REFRESH_API_KEY= (optional, for cron auth)
ALLOWED_ORIGINS=https://confcontrarian.com,https://www.confcontrarian.com

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

# Run data refresh
python -m backend.data_collection.daily_refresh

# Refresh just Haslametrics (fast, no login required)
python -m backend.data_collection.haslametrics_scraper

# Refresh just KenPom (requires subscription)
python -m backend.data_collection.kenpom_scraper
```

## Data Flow

1. **Daily at 6 AM EST** - GitHub Actions triggers `/refresh`
2. **Refresh Pipeline:**
   - Fetches spreads + moneylines from The Odds API
   - Refreshes KenPom advanced analytics (if credentials configured)
   - Refreshes Haslametrics analytics (FREE - no login required)
   - Creates/updates games in Supabase
   - Runs predictions on upcoming games
   - Runs Claude AI analysis on today's games
3. **Frontend** reads from Supabase views
4. **Users** can trigger AI analysis on-demand via button (Claude or Grok)

## AI Analysis

The AI service (`backend/api/ai_service.py`) uses Claude and Grok to analyze games:

### Dual-Provider System
- **Claude** (Anthropic) - Primary AI provider
- **Grok** (xAI) - Secondary AI for comparison, uses OpenAI-compatible API

### Analysis Flow
1. Builds context with team rankings, spread, moneylines, venue, conference
2. Includes **KenPom data** when available: AdjO, AdjD, efficiency margin, tempo, SOS, luck
3. Includes **Haslametrics data** when available: All-Play %, momentum (O/D), efficiency, quadrant records
4. When both analytics sources available, prompt instructs AI to cross-validate
5. Parses JSON response with: recommended_bet, confidence_score, key_factors, reasoning
6. Stores analysis in `ai_analysis` table with `ai_provider` field

### KenPom Integration
- Requires paid subscription credentials
- Uses `kenpompy` library with Selenium browser automation
- Fetches: AdjO, AdjD, AdjEM, Tempo, SOS, Luck for 350+ teams
- Stored in `kenpom_ratings` table with daily snapshots

### Haslametrics Integration
- **FREE** - no subscription required
- Fetches from XML endpoint: `https://haslametrics.com/ratings{YY}.xml`
- Uses "All-Play Percentage" methodology (win % vs average D1 team)
- Key metrics: All-Play %, Momentum (overall/offense/defense), Efficiency, Quadrant records
- Requires `brotli` package for Brotli decompression (server uses `Content-Encoding: br`)
- Stored in `haslametrics_ratings` table with daily snapshots

## Current Status

**Working:**
- Dashboard with table view of today's games and AI-powered picks
- Game detail pages with full AI analysis
- **Dual AI providers:** Claude and Grok analysis on every game
- **Dual analytics sources:** KenPom AND Haslametrics data displayed
- "Run AI Analysis" button with provider selection (Claude/Grok)
- Daily refresh pipeline (GitHub Actions)
- KenPom advanced analytics integration
- Haslametrics advanced analytics integration (FREE)
- AI analysis enhanced with both KenPom and Haslametrics data
- AI cross-validates between analytics sources when both available
- SQL views prioritize AI analysis over baseline predictions
- Spread-based probability heuristics for baseline model
- Compact table view with games showing Pick, Confidence, and Edge
- Moneyline data capture and display
- Custom domain: confcontrarian.com
- Security hardening (CORS validation, input sanitization, error handling)

**In Progress:**
- Performance tracking page (placeholder, needs real data)
- March Madness bracket page (placeholder, ready for Selection Sunday)

## Roadmap / Future Features

### Phase 1: Authentication & User Accounts
- Supabase Auth integration
- User profiles
- Saved preferences (favorite teams, notification settings)

### Phase 2: Bet Tracking System
- "Bet Card" feature - users can add picks to their card
- Track bet outcomes (win/loss/push)
- Personal performance metrics:
  - Win rate by confidence tier
  - ROI tracking
  - Streak tracking
  - Units won/lost
- Historical bet history

### Phase 3: Subscription/Paywall
- Stripe integration
- Tiered access:
  - Free: Basic game info, limited AI analysis
  - Pro: Full AI analysis, both providers, advanced analytics
  - Premium: Alerts, custom filters, API access
- Trial period

### Phase 4: Enhanced Features
- Email/push notifications for high-confidence picks
- Custom filters (by conference, ranked teams only, etc.)
- Historical backtesting results
- Mobile app (React Native)

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

### Add a new analytics source
1. Create scraper in `backend/data_collection/`
2. Create database migration for new table
3. Update `daily_refresh.py` to include new scraper
4. Update `ai_service.py` to fetch data in `build_game_context()`
5. Update `build_analysis_prompt()` to include new data
6. Update frontend types and display components

## Notes

- Frontend shows empty states when Supabase isn't configured (no demo data)
- The Odds API free tier: 500 requests/month
- Railway auto-deploys on git push
- Vercel auto-deploys on git push
- KenPom requires paid subscription - scraper uses browser automation via Selenium
- Haslametrics is FREE - uses direct XML endpoint with Brotli compression
- AI analysis stored in `ai_analysis` table with `ai_provider` field (claude/grok)
- Both AI providers receive identical prompts with all available analytics data

## Troubleshooting

### 405 Method Not Allowed on AI Analysis
- Check that `NEXT_PUBLIC_API_URL` in Vercel includes `https://`
- Check that `ALLOWED_ORIGINS` in Railway includes your exact domain(s)

### KenPom data all NULL
- Ensure using `get_pomeroy_ratings()` not `get_efficiency()` in kenpom_scraper.py
- Check Railway logs for actual column names returned by kenpompy

### Haslametrics fetch fails
- Ensure `brotli` package is installed (server returns Brotli-compressed XML)
- Check User-Agent headers are set (server blocks requests without them)
- Test endpoint directly: `curl https://web-production-e5efb.up.railway.app/refresh-haslametrics`

### React Hydration Error #418
- Usually caused by `new Date()` in server components (different on server vs client)
- Use static dates or move date logic to client components

### Full refresh timeout (502 error)
- Full `/refresh` can take 5+ minutes (KenPom login, all scrapers, AI analysis)
- Use individual endpoints for testing: `/refresh-haslametrics`, `/regenerate-predictions`
- Railway may timeout long-running requests - consider background job architecture

## Security Features

The codebase includes security hardening:

### Backend (`main.py`)
- CORS origin validation (rejects wildcards, validates format)
- Global exception handler (logs errors server-side, returns generic messages to client)
- Input validation on all endpoints
- Rate limiting ready (can be added)

### Database (`supabase_client.py`)
- UUID validation on all ID parameters
- String sanitization (length limits, null byte removal)
- Parameterized queries via Supabase SDK
- Service key kept server-side only

### General
- No secrets in client-side code
- HTTPS enforced on all endpoints
- Logging avoids leaking sensitive data
