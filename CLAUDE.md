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
- Dashboard with real games and spreads
- Game detail pages with AI analysis
- "Run AI Analysis" button on game pages
- Daily refresh pipeline (GitHub Actions)
- KenPom advanced analytics integration
- AI analysis enhanced with KenPom data
- Performance tracking page (demo data)
- March Madness preview page

**Pending/Future:**
- User authentication (Supabase Auth)
- Payment/subscription (Stripe)
- Custom domain
- Bet result tracking
- Email notifications for high-confidence picks
- Haslametrics integration (no API, requires Selenium)
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

- Frontend uses demo data fallback when Supabase isn't configured
- The Odds API free tier: 500 requests/month
- Railway auto-deploys on git push
- Vercel auto-deploys on git push
- KenPom requires paid subscription - scraper uses browser automation via Selenium

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
