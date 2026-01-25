# Conference Contrarian

AI-powered college basketball betting analysis. Find edges, get recommendations, track performance.

![Status](https://img.shields.io/badge/status-live-brightgreen)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Claude](https://img.shields.io/badge/AI-Claude-orange)
![Grok](https://img.shields.io/badge/AI-Grok-blue)

**Live Site:** [confcontrarian.com](https://confcontrarian.com)

---

## Table of Contents

- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [API Keys Setup](#api-keys-setup)
- [Local Development Setup](#local-development-setup)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Supabase Configuration](#supabase-configuration)
- [Daily Data Pipeline](#daily-data-pipeline)
- [Deployment](#deployment)
  - [Railway (Backend)](#railway-backend)
  - [Vercel (Frontend)](#vercel-frontend)
  - [Multi-Service Architecture](#multi-service-architecture)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [License](#license)

---

## Features

- **Real-time Spreads & Moneylines** - Current betting lines from The Odds API
- **Dual AI Analysis** - Claude AND Grok-powered game breakdowns with betting recommendations
- **Advanced Analytics** - KenPom and Haslametrics integration for deep statistical analysis
- **Prediction Markets** - Polymarket and Kalshi integration with arbitrage detection
- **Confidence Tiers** - High/Medium/Low picks based on edge detection
- **Performance Tracking** - ROI, win rate, and streak tracking
- **March Madness Ready** - Tournament bracket view and analysis

---

## Architecture Overview

```
                                    +------------------+
                                    |    Vercel        |
                                    |   (Frontend)     |
                                    |   Next.js 16     |
                                    +--------+---------+
                                             |
                                             | HTTPS
                                             v
+------------------+              +------------------+              +------------------+
|   The Odds API   |  -------->  |    Railway       |  <--------   |    Supabase      |
|   KenPom         |             |   (Backend)      |              |   (Database)     |
|   Haslametrics   |             |   FastAPI        |              |   PostgreSQL     |
|   ESPN           |             |   Python 3.11    |              +------------------+
|   Polymarket     |              +--------+---------+
|   Kalshi         |                       |
+------------------+                       |
                                           v
                              +---------------------------+
                              |       AI Services         |
                              |  Claude (Anthropic)       |
                              |  Grok (xAI)               |
                              +---------------------------+
```

| Service | Purpose | Platform |
|---------|---------|----------|
| Frontend | User interface, game display | Vercel |
| Backend API | Data processing, AI orchestration | Railway |
| Database | Game data, predictions, analytics | Supabase |
| AI Analysis | Betting recommendations | Claude + Grok APIs |
| Data Sources | Spreads, analytics, markets | Various APIs |

---

## Prerequisites

- **Node.js** 18+ (for frontend)
- **Python** 3.11+ (for backend)
- **Git** (for version control)
- **Accounts needed:**
  - Supabase (free tier works)
  - Anthropic (Claude API)
  - The Odds API (free tier: 500 requests/month)
  - Optional: xAI (Grok API), KenPom subscription

---

## API Keys Setup

### Required API Keys

| Key | Where to Get It | Purpose |
|-----|-----------------|---------|
| `SUPABASE_URL` | [Supabase Dashboard](https://app.supabase.com) > Project Settings > API | Database connection |
| `SUPABASE_SERVICE_KEY` | Same location (use "service_role" key) | Backend database access |
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/) | Claude AI analysis |
| `ODDS_API_KEY` | [The Odds API](https://the-odds-api.com/) | Betting lines data |

### Optional API Keys

| Key | Where to Get It | Purpose |
|-----|-----------------|---------|
| `GROK_API_KEY` | [xAI](https://x.ai/) | Secondary AI analysis |
| `KENPOM_EMAIL` / `KENPOM_PASSWORD` | [KenPom](https://kenpom.com/) ($20/year subscription) | Advanced analytics |
| `KALSHI_API_KEY` / `KALSHI_PRIVATE_KEY_PATH` | [Kalshi](https://kalshi.com/) | Prediction market data |
| `REFRESH_API_KEY` | Generate yourself | Secure refresh endpoint |

### API Key Formats

```bash
# Anthropic (Claude) - starts with sk-ant-api
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx...

# xAI (Grok) - starts with xai-
GROK_API_KEY=xai-xxxxx...

# The Odds API - 32-character hex string
ODDS_API_KEY=a1b2c3d4e5f6g7h8i9j0...

# Supabase URL - https://<project-id>.supabase.co
SUPABASE_URL=https://abcdefghij.supabase.co

# Supabase Service Key - long JWT token
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6...
```

---

## Local Development Setup

### Backend Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/march-madness.git
   cd march-madness
   ```

2. **Create Python virtual environment:**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create backend environment file:**
   ```bash
   # Copy the root example (or use backend/.env.example for more detailed comments)
   cp .env.example .env
   # OR
   cp backend/.env.example .env
   ```

5. **Edit `.env` with your API keys:**
   ```env
   # Required
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=your-service-role-key
   ANTHROPIC_API_KEY=sk-ant-api03-your-key
   ODDS_API_KEY=your-odds-api-key

   # Optional
   GROK_API_KEY=xai-your-key
   KENPOM_EMAIL=your@email.com
   KENPOM_PASSWORD=your-password

   # CORS - localhost for development
   ALLOWED_ORIGINS=http://localhost:3000
   ```

6. **Start the backend server:**
   ```bash
   uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Verify backend is running:**
   ```bash
   curl http://localhost:8000/health
   ```
   You should see:
   ```json
   {
     "status": "healthy",
     "supabase_configured": true,
     "claude_configured": true,
     ...
   }
   ```

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

3. **Create frontend environment file:**
   ```bash
   # Create .env.local in the frontend directory
   ```

4. **Edit `frontend/.env.local`:**
   ```env
   # Supabase (for client-side reads)
   NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key

   # Backend API URL - MUST include https:// in production
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

   > **IMPORTANT:** The `NEXT_PUBLIC_API_URL` MUST include the protocol (`http://` or `https://`). Without it, fetch requests will fail with 405 errors.

5. **Start the frontend development server:**
   ```bash
   npm run dev
   ```

6. **Open in browser:**
   Navigate to [http://localhost:3000](http://localhost:3000)

### Running Both Services

For local development, run both services in separate terminals:

```bash
# Terminal 1 - Backend
cd march-madness
venv\Scripts\activate  # or source venv/bin/activate on Mac/Linux
uvicorn backend.api.main:app --reload

# Terminal 2 - Frontend
cd march-madness/frontend
npm run dev
```

---

## Supabase Configuration

### 1. Create a Supabase Project

1. Go to [app.supabase.com](https://app.supabase.com)
2. Click "New Project"
3. Choose organization, name, and region (US East recommended)
4. Set a strong database password (save it!)
5. Wait for project to provision (~2 minutes)

### 2. Get Your API Keys

1. Go to Project Settings > API
2. Copy these values:
   - **Project URL** -> `SUPABASE_URL`
   - **anon public** key -> `NEXT_PUBLIC_SUPABASE_ANON_KEY` (frontend)
   - **service_role** key -> `SUPABASE_SERVICE_KEY` (backend only!)

> **Security Warning:** Never expose the service_role key in frontend code!

### 3. Run Database Migrations

Execute these SQL files in order via Supabase SQL Editor:

```
supabase/migrations/
├── 20250118000000_initial_schema.sql        # Core tables
├── 20250118000001_today_games_view.sql      # Game views
├── 20250119000000_kenpom_ratings.sql        # KenPom analytics
├── 20250120000000_ai_priority_view.sql      # AI analysis views
├── 20250121000000_haslametrics_ratings.sql  # Haslametrics
├── 20250121000001_fix_sports_betting_rls.sql
├── 20250121100000_add_performance_indexes.sql
├── 20250122000000_fix_timezone_views.sql
├── 20260122000000_prediction_markets.sql    # PM integration
├── 20260122000001_add_prediction_market_flags.sql
└── 20260123000000_fix_tip_time_in_views.sql
```

**To run migrations:**
1. Open Supabase Dashboard > SQL Editor
2. Click "New Query"
3. Paste each migration file content (in order)
4. Click "Run"

### Database Schema Overview

**Core Tables:**
| Table | Purpose |
|-------|---------|
| `teams` | 416 NCAA teams with conferences |
| `games` | Game schedules, scores, metadata |
| `spreads` | Betting lines (spread, ML, total) |
| `rankings` | AP poll rankings by week |
| `predictions` | Model predictions per game |
| `ai_analysis` | Claude/Grok analysis results |
| `bet_results` | Bet outcome tracking |
| `kenpom_ratings` | KenPom advanced analytics |
| `haslametrics_ratings` | Haslametrics analytics |
| `prediction_markets` | Polymarket/Kalshi data |
| `arbitrage_opportunities` | Detected edges |

**Key Views:**
| View | Purpose |
|------|---------|
| `today_games` | Today's games with all joined data |
| `upcoming_games` | Next 7 days of games |
| `latest_kenpom_ratings` | Most recent KenPom per team |
| `latest_haslametrics_ratings` | Most recent Haslametrics per team |
| `actionable_arbitrage` | Arbitrage opportunities >=10% edge |

---

## Daily Data Pipeline

The application uses an automated daily refresh to keep data current.

### Pipeline Steps

The `/refresh` endpoint runs these steps in order:

1. **Fetch Spreads** - Get current lines from The Odds API
2. **Refresh KenPom** - Update advanced analytics (if credentials set)
3. **Refresh Haslametrics** - Update All-Play metrics (FREE)
4. **Refresh ESPN Times** - Get accurate tip-off times
5. **Refresh Prediction Markets** - Polymarket + Kalshi data
6. **Run Predictions** - Generate model predictions for upcoming games
7. **Update Results** - Score completed games
8. **Run AI Analysis** - Claude analysis for today's games

### Running the Pipeline Manually

**Via API (recommended):**
```bash
# Full refresh
curl -X POST https://your-railway-url.up.railway.app/refresh

# Just Haslametrics (fast, no auth needed)
curl -X POST https://your-railway-url.up.railway.app/refresh-haslametrics

# Just predictions
curl -X POST https://your-railway-url.up.railway.app/regenerate-predictions

# Just ESPN tip times
curl -X POST https://your-railway-url.up.railway.app/refresh-espn-times
```

**Via Python (local development):**
```bash
# Activate virtual environment first
python -m backend.data_collection.daily_refresh

# Individual scrapers
python -m backend.data_collection.haslametrics_scraper
python -m backend.data_collection.kenpom_scraper  # Requires credentials
```

### GitHub Actions Automation

The pipeline runs automatically at 6 AM EST daily via GitHub Actions.

**Setup:**
1. Go to your GitHub repo > Settings > Secrets and variables > Actions
2. Add these secrets:
   - `RAILWAY_API_URL` - Your Railway backend URL (e.g., `https://web-production-e5efb.up.railway.app`)
   - `REFRESH_API_KEY` - Optional authentication key

**Workflow file:** `.github/workflows/daily-refresh.yml`

**Manual trigger:**
1. Go to Actions tab in GitHub
2. Select "Daily Data Refresh"
3. Click "Run workflow"

### Pipeline Timing Notes

| Operation | Typical Duration |
|-----------|------------------|
| Odds API fetch | 5-10 seconds |
| Haslametrics refresh | 10-20 seconds |
| KenPom refresh | 60-120 seconds (browser automation) |
| ESPN tip times | 5-10 seconds |
| Prediction markets | 15-30 seconds |
| AI analysis (per game) | 3-5 seconds |
| **Full refresh** | **3-5 minutes** |

> **Warning:** Full refresh can take 5+ minutes. Railway may timeout on very long requests.

---

## Deployment

### Railway (Backend)

1. **Create Railway Account:**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub

2. **Create New Project:**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your march-madness repository

3. **Configure Environment Variables:**
   Go to your service > Variables and add:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=your-service-key
   ANTHROPIC_API_KEY=sk-ant-api03-...
   GROK_API_KEY=xai-...
   ODDS_API_KEY=your-key
   KENPOM_EMAIL=your@email.com
   KENPOM_PASSWORD=your-password
   ALLOWED_ORIGINS=https://confcontrarian.com,https://www.confcontrarian.com
   REFRESH_API_KEY=your-secret-key
   ```

4. **Verify Deployment:**
   - Railway auto-deploys from `Procfile` and `railway.json`
   - Check the "Deployments" tab for build logs
   - Test: `curl https://your-app.up.railway.app/health`

5. **Custom Domain (Optional):**
   - Go to Settings > Networking > Public Networking
   - Add your custom domain

### Vercel (Frontend)

1. **Import Project:**
   - Go to [vercel.com](https://vercel.com)
   - Click "Add New" > "Project"
   - Import your GitHub repository

2. **Configure Build Settings:**
   - Framework Preset: Next.js
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `.next`

3. **Set Environment Variables:**
   Go to Settings > Environment Variables:
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
   NEXT_PUBLIC_API_URL=https://your-railway-app.up.railway.app
   ```

   > **CRITICAL:** `NEXT_PUBLIC_API_URL` MUST include `https://`

4. **Deploy:**
   - Vercel auto-deploys on push to main
   - Check the "Deployments" tab for status

5. **Custom Domain:**
   - Go to Settings > Domains
   - Add your domain (e.g., `confcontrarian.com`)
   - Configure DNS records as instructed

### Multi-Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         PRODUCTION                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐  │
│  │   Vercel     │      │   Railway    │      │  Supabase │  │
│  │   Frontend   │ ───> │   Backend    │ ───> │  Database │  │
│  │              │      │              │      │           │  │
│  │ confcontrarian│      │ FastAPI      │      │ PostgreSQL│  │
│  │   .com       │      │ Python 3.11  │      │           │  │
│  └──────────────┘      └──────────────┘      └───────────┘  │
│         │                     │                    │         │
│         │              ┌──────┴──────┐             │         │
│         │              │             │             │         │
│         │         ┌────▼────┐   ┌────▼────┐       │         │
│         │         │ Claude  │   │  Grok   │       │         │
│         │         │   API   │   │   API   │       │         │
│         │         └─────────┘   └─────────┘       │         │
│         │                                          │         │
│         └──────────────────────────────────────────┘         │
│                      (Direct DB reads)                       │
└─────────────────────────────────────────────────────────────┘
```

**Service Communication:**
- Frontend -> Backend: HTTPS REST API
- Frontend -> Supabase: Direct reads (anon key)
- Backend -> Supabase: Full access (service key)
- Backend -> AI APIs: HTTPS

**Environment Variables by Service:**

| Variable | Vercel | Railway | Supabase |
|----------|--------|---------|----------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | - | - |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | - | - |
| `NEXT_PUBLIC_API_URL` | Yes | - | - |
| `SUPABASE_URL` | - | Yes | - |
| `SUPABASE_SERVICE_KEY` | - | Yes | - |
| `ANTHROPIC_API_KEY` | - | Yes | - |
| `GROK_API_KEY` | - | Yes | - |
| `ODDS_API_KEY` | - | Yes | - |
| `ALLOWED_ORIGINS` | - | Yes | - |

---

## Troubleshooting

### Common Issues

#### 1. 405 Method Not Allowed on AI Analysis

**Symptom:** POST to `/ai-analysis` returns 405

**Cause:** Missing `https://` in `NEXT_PUBLIC_API_URL`

**Fix:**
```env
# Wrong
NEXT_PUBLIC_API_URL=your-app.up.railway.app

# Correct
NEXT_PUBLIC_API_URL=https://your-app.up.railway.app
```

#### 2. CORS Errors

**Symptom:** Browser console shows CORS blocked errors

**Cause:** Frontend origin not in `ALLOWED_ORIGINS`

**Fix:** In Railway environment variables:
```env
ALLOWED_ORIGINS=https://confcontrarian.com,https://www.confcontrarian.com,http://localhost:3000
```

#### 3. Supabase Connection Failed

**Symptom:** "Invalid SUPABASE_URL format" or connection errors

**Checks:**
- URL format: `https://<project-id>.supabase.co` (no trailing slash)
- Service key: Use "service_role" not "anon" for backend
- Project is not paused (free tier pauses after 1 week inactivity)

#### 4. KenPom Data All NULL

**Symptom:** KenPom analytics show NULL values

**Causes:**
- Wrong kenpompy function (use `get_pomeroy_ratings()`)
- KenPom credentials invalid
- Selenium/Chrome issues on Railway

**Debug:**
```bash
python -c "from kenpompy.misc import get_pomeroy_ratings; print('Import OK')"
```

#### 5. Haslametrics Fetch Fails

**Symptom:** Haslametrics refresh returns error

**Checks:**
- `brotli` package installed (server uses Brotli compression)
- User-Agent header set (server blocks requests without it)

**Test:**
```bash
curl -X POST https://your-railway-url/refresh-haslametrics
```

#### 6. Full Refresh Times Out (502)

**Symptom:** `/refresh` returns 502 Gateway Timeout

**Cause:** Full refresh takes 5+ minutes, exceeds Railway timeout

**Solutions:**
- Use individual endpoints: `/refresh-haslametrics`, `/regenerate-predictions`
- Increase Railway timeout settings
- Run locally for full refresh

#### 7. React Hydration Error #418

**Symptom:** Console shows hydration mismatch warning

**Cause:** `new Date()` in server components renders different value on client

**Fix:** Move date logic to client components with `'use client'` directive

#### 8. Empty Dashboard (No Games)

**Symptom:** Dashboard shows "No games today"

**Checks:**
- Run `/refresh` to populate data
- Check Supabase has data in `games` table
- Verify date timezone (uses US Eastern)

#### 9. AI Analysis Returns Generic Error

**Symptom:** AI analysis fails with "please try again"

**Debug endpoint:**
```bash
curl https://your-railway-url/debug/ai-analysis/{game_id}?provider=claude
```

This returns detailed step-by-step error information.

### Data Collection Pipeline Issues

#### 10. The Odds API Quota Exceeded

**Symptom:** Spread data not updating, API returns 401/429

**Causes:**
- Free tier limit reached (500 requests/month)
- API key invalid or expired

**Checks:**
```bash
# Check remaining quota
curl "https://api.the-odds-api.com/v4/sports?apiKey=YOUR_KEY"
# Look for x-requests-remaining header
```

**Fix:** Upgrade to paid tier or wait for monthly reset

#### 11. Team Name Matching Failures

**Symptom:** Many "Could not match team" messages in logs

**Cause:** External source uses different team names than our database

**Debug:**
```bash
# Check which teams are in database
python -c "
from backend.api.supabase_client import get_supabase
client = get_supabase()
result = client.table('teams').select('name, normalized_name').execute()
for t in result.data[:10]:
    print(f'{t[\"name\"]} -> {t[\"normalized_name\"]}')"
```

**Fix:** Add name mappings in the respective scraper's `normalize_team_name()` function

#### 12. Odds API Returns Empty Games

**Symptom:** No games found even during season

**Causes:**
- Wrong sport key (should be `basketball_ncaab`)
- Markets parameter incorrect
- API outage

**Debug:**
```bash
curl "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds?apiKey=YOUR_KEY&regions=us&markets=spreads,totals"
```

#### 13. KenPom Browser Automation Fails

**Symptom:** "Chrome not found" or "WebDriver error"

**Cause:** Railway doesn't have Chrome/Chromium installed by default

**Solutions:**
1. Use Railway's Chrome buildpack
2. Run KenPom refresh locally instead
3. Use kenpompy's headless mode if available

```bash
# Test kenpompy locally
python -c "
from kenpompy.utils import login
browser = login('your@email.com', 'password')
print('Login successful!')
browser.close()"
```

#### 14. Prediction Market Matching Issues

**Symptom:** Markets found but not matched to games/teams

**Cause:** Market titles don't match team names in database

**Debug:**
```bash
curl https://your-railway-url/debug-pm-match
```

**Fix:** Review market titles and add team name mappings in `prediction_market_scraper.py`

#### 15. Cache Serving Stale Data

**Symptom:** Analytics data not updating after refresh

**Cause:** Cache TTL (1 hour) not expired

**Fix:** Cache is automatically invalidated during refresh, but if needed:
```python
from backend.api.supabase_client import invalidate_ratings_cache
result = invalidate_ratings_cache()
print(result)  # Shows count of invalidated entries
```

### Useful Debug Commands

```bash
# Check backend health
curl https://your-railway-url/health

# Check API key configuration (safe - only returns booleans)
curl https://your-railway-url/health | jq

# Test Supabase connection
curl https://your-railway-url/today

# View Railway logs
railway logs

# Test local backend
uvicorn backend.api.main:app --reload
curl http://localhost:8000/health
```

---

## Project Structure

```
march-madness/
├── frontend/                    # Next.js 16 application
│   ├── src/
│   │   ├── app/                # App Router pages
│   │   │   ├── page.tsx        # Dashboard (today's games)
│   │   │   ├── games/          # Games listing and detail
│   │   │   ├── march-madness/  # Tournament bracket
│   │   │   └── performance/    # Stats tracking
│   │   ├── components/         # React components
│   │   └── lib/                # Utilities, types, Supabase client
│   ├── package.json
│   └── .env.local              # Frontend env vars
│
├── backend/
│   ├── api/
│   │   ├── main.py             # FastAPI application
│   │   ├── supabase_client.py  # Database operations
│   │   ├── ai_service.py       # Claude + Grok integration
│   │   ├── middleware.py       # Logging, rate limiting
│   │   └── secrets_validator.py
│   ├── data_collection/
│   │   ├── daily_refresh.py    # Main pipeline
│   │   ├── kenpom_scraper.py   # KenPom (requires subscription)
│   │   ├── haslametrics_scraper.py  # Haslametrics (FREE)
│   │   ├── espn_scraper.py     # ESPN tip times
│   │   ├── polymarket_client.py
│   │   ├── kalshi_client.py
│   │   └── arbitrage_detector.py
│   ├── models/
│   │   └── baseline.py         # Prediction models
│   └── tests/                  # pytest tests
│
├── supabase/
│   └── migrations/             # SQL schema files
│
├── .github/
│   └── workflows/
│       └── daily-refresh.yml   # Cron job
│
├── .env                        # Backend env vars (gitignored)
├── .env.example                # Template
├── Procfile                    # Railway deployment
├── railway.json                # Railway config
├── runtime.txt                 # Python version
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## API Reference

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with API status |
| `/today` | GET | Today's games with spreads and predictions |
| `/games` | GET | Upcoming games (pagination supported) |
| `/games/{id}` | GET | Single game details |
| `/games/{id}/analytics` | GET | KenPom + Haslametrics for a game |
| `/predict` | POST | Get prediction for a game |
| `/ai-analysis` | POST | Run Claude or Grok analysis |
| `/stats` | GET | Season performance statistics |
| `/rankings` | GET | Current AP rankings |

### Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/refresh` | POST | Full daily data refresh |
| `/refresh-haslametrics` | POST | Haslametrics only (fast) |
| `/refresh-espn-times` | POST | ESPN tip times only |
| `/regenerate-predictions` | POST | Regenerate predictions |
| `/debug/ai-analysis/{id}` | GET | Debug AI analysis flow |

### Rate Limits

- Standard endpoints: 30 requests/minute/IP
- AI endpoints: 5 requests/minute/IP

---

## License

Private project. All rights reserved.

---

## Acknowledgments

- [CBBpy](https://github.com/dcstats/CBBpy) - NCAA basketball data
- [kenpompy](https://github.com/j-andrews7/kenpompy) - KenPom scraper
- [The Odds API](https://the-odds-api.com) - Betting lines
- [Haslametrics](https://haslametrics.com) - Free advanced analytics
- [Supabase](https://supabase.com) - Database and auth
- [Claude](https://anthropic.com) - AI analysis
- [Grok](https://x.ai) - AI analysis

---

Built with Claude Code. For entertainment purposes only. Please gamble responsibly.
