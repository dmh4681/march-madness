# Conference Contrarian: From Bar Napkin to Production

## The Complete Journey of Building a Betting App with AI Assistance

---

## Chapter 1: The Drunk Idea (The Spark)

**Setting:** A bar with a friend, watching college basketball, March Madness on the horizon.

**The Observation:** "You know what I've noticed? When top-ranked teams play conference games, they seem to cover the spread way more often. Like the public underestimates how much pride is on the line."

**The Hypothesis:** Top 5 ranked teams in conference play have a statistically significant edge against the spread.

**The Question:** "What if we could build something that finds these edges and tells us which games to bet?"

---

## Chapter 2: The Initial Prompt to Claude

The next morning, still buzzing from the idea, the first prompt was sent:

```
I have a hypothesis about college basketball betting. I think top-ranked
teams (AP Top 5) perform better against the spread in conference games
because of pride, preparation, and the "prove it" factor.

Can you help me:
1. Validate this hypothesis with historical data
2. Build a system to identify these opportunities going forward
3. Create a dashboard to track performance
```

**What Claude Did:**
- Asked clarifying questions about data sources, timeframes, and tech preferences
- Suggested a systematic approach: data collection → validation → infrastructure → frontend
- Identified potential data sources (CBBpy, The Odds API)

---

## Chapter 3: Data Collection & Validation

### The Data Hunt

Claude helped write Python scripts to collect:
- **6,391 NCAA basketball games** (2020-2024 seasons)
- **AP Rankings** by week for each season
- **Current betting spreads** from The Odds API

```python
# Using CBBpy to collect game data
from cbbpy.mens_scraper import get_games

# 5 seasons of D1 basketball
games_df = get_games(season=2024, game_type='regular')
```

### The Hypothesis Test

Results of the analysis:

| Metric | Value |
|--------|-------|
| Top 5 teams ATS in conference games | 56.8% |
| Sample size | 347 games |
| P-value | 0.121 |
| Expected by chance | 50% |

**The Verdict:** Promising trend, but not statistically significant (p > 0.05).

**The Decision:** Build the framework anyway. The infrastructure has value beyond one hypothesis - it can test many betting strategies.

---

## Chapter 4: Architecture Planning

### The Stack Decision

Through conversation with Claude, the architecture emerged:

```
┌─────────────────────────────────────────┐
│              VERCEL                      │
│    Next.js Frontend (Dashboard)          │
└───────────────┬─────────────────────────┘
                │
    ┌───────────┴───────────┐
    ▼                       ▼
┌─────────────┐    ┌─────────────────┐
│  SUPABASE   │    │  RAILWAY        │
│  PostgreSQL │    │  Python/FastAPI │
│  Database   │    │  ML Models      │
└─────────────┘    │  AI Analysis    │
                   └─────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        ┌──────────┐            ┌──────────┐
        │  Claude  │            │   Grok   │
        │   API    │            │   API    │
        └──────────┘            └──────────┘
```

### Key Decisions Made

1. **Supabase over raw PostgreSQL** - Managed, has good free tier, instant APIs
2. **Railway over AWS Lambda** - Simpler for Python ML code, keeps Python backend separate
3. **Next.js on Vercel** - Fast deploys, good DX, handles SSR for SEO
4. **Dual AI (Claude + Grok)** - Compare analyses, consensus picks

---

## Chapter 5: Database Design

Claude generated the complete schema:

```sql
-- Core tables
CREATE TABLE teams (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT UNIQUE,
  conference TEXT,
  is_power_conference BOOLEAN
);

CREATE TABLE games (
  id UUID PRIMARY KEY,
  date DATE NOT NULL,
  season INTEGER NOT NULL,
  home_team_id UUID REFERENCES teams(id),
  away_team_id UUID REFERENCES teams(id),
  home_score INTEGER,
  away_score INTEGER,
  is_conference_game BOOLEAN
);

CREATE TABLE spreads (
  id UUID PRIMARY KEY,
  game_id UUID REFERENCES games(id),
  home_spread DECIMAL(4,1),
  over_under DECIMAL(4,1),
  captured_at TIMESTAMPTZ
);

CREATE TABLE predictions (
  id UUID PRIMARY KEY,
  game_id UUID REFERENCES games(id),
  model_name TEXT,
  predicted_home_cover_prob DECIMAL,
  confidence_tier TEXT,
  recommended_bet TEXT
);

CREATE TABLE ai_analysis (
  id UUID PRIMARY KEY,
  game_id UUID REFERENCES games(id),
  ai_provider TEXT,  -- 'claude' or 'grok'
  reasoning TEXT,
  recommended_bet TEXT,
  confidence_score DECIMAL
);
```

---

## Chapter 6: The Build

### Day 1: Infrastructure

```bash
# Commands run to set up the project
npx create-next-app@latest frontend --typescript --tailwind
pip install fastapi uvicorn supabase anthropic
```

### Files Created

**Frontend (Next.js)**
```
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx              # Dashboard
│   │   ├── games/
│   │   │   ├── page.tsx          # All games listing
│   │   │   └── [id]/page.tsx     # Game detail
│   │   ├── march-madness/
│   │   │   └── page.tsx          # Tournament bracket
│   │   └── performance/
│   │       └── page.tsx          # Stats & ROI
│   ├── components/
│   │   ├── GameCard.tsx
│   │   ├── ConfidenceBadge.tsx
│   │   ├── PicksList.tsx
│   │   └── AIAnalysis.tsx
│   └── lib/
│       ├── supabase.ts
│       ├── types.ts
│       └── api.ts
```

**Backend (Python/FastAPI)**
```
backend/
├── api/
│   ├── main.py           # FastAPI endpoints
│   ├── supabase_client.py
│   └── ai_service.py     # Claude/Grok integration
├── models/
│   └── baseline.py       # ML prediction models
└── data_collection/
    ├── scraper.py        # CBBpy data collection
    ├── rankings.py       # AP rankings scraper
    └── migrate_to_supabase.py
```

### The Migration

```bash
python -m backend.data_collection.migrate_to_supabase
```

Output:
```
============================================================
Conference Contrarian - Data Migration to Supabase
============================================================

=== Migrating Teams ===
Found 451 unique teams
Created/verified 451 teams

=== Migrating Games ===
Loaded 6391 games from CSV
Migrated 6391 games, skipped 0, errors 0

=== Migrating Rankings ===
Migrated 125 rankings

============================================================
Migration complete!
============================================================
```

---

## Chapter 7: Deployment

### Vercel (Frontend)

1. Connect GitHub repo
2. Set root directory to `frontend`
3. Add environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
4. Deploy

**Build Error #1:** Module not found `@/lib/supabase`
- **Cause:** Files not committed to git
- **Fix:** `git add -f frontend/src/lib/`

**Build Error #2:** Missing `baseUrl` in tsconfig
- **Cause:** Path aliases need baseUrl
- **Fix:** Added `"baseUrl": "."` to tsconfig.json

### Railway (Backend)

1. Connect GitHub repo
2. Add environment variables:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `ANTHROPIC_API_KEY`
   - `ALLOWED_ORIGINS`
3. Deploy

**Files needed:**
```
Procfile: web: uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT
runtime.txt: python-3.11.7
railway.json: {"deploy": {"startCommand": "..."}}
```

---

## Chapter 8: The Final Product

### What We Built

1. **Dashboard** - Today's games with AI-powered confidence ratings
2. **All Games** - Upcoming schedule with filters
3. **March Madness** - Tournament bracket preview and analysis
4. **Performance** - Historical ROI, win rates, streaks
5. **Game Detail** - Deep dive with AI analysis from Claude & Grok
6. **API** - Endpoints for predictions, analysis, stats

### Live URLs

- **Frontend:** `https://your-app.vercel.app`
- **Backend API:** `https://web-production-xxxx.up.railway.app`
- **Health Check:** `/health`

### Tech Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | Next.js 16, Tailwind | Dashboard UI |
| Backend | FastAPI, Python | ML & AI orchestration |
| Database | Supabase (PostgreSQL) | Data storage |
| AI | Claude API, Grok API | Game analysis |
| Data | CBBpy, The Odds API | Games & spreads |
| Hosting | Vercel, Railway | Deployment |

---

## Chapter 9: What's Next

### Immediate Improvements
- [ ] Connect real-time spreads from The Odds API
- [ ] Train ML models on historical data
- [ ] Set up daily cron job for data refresh
- [ ] Add email notifications for high-confidence picks

### March Madness Features
- [ ] Full 68-team bracket visualization
- [ ] Round-by-round predictions
- [ ] Upset probability calculator
- [ ] Pool optimization suggestions

### Long-term Vision
- [ ] Backtest different betting strategies
- [ ] Track actual bet results
- [ ] Mobile app version
- [ ] Community features (share picks)

---

## Chapter 10: Lessons Learned

### On Building with AI Assistance

1. **Start with the hypothesis, not the code** - Claude helped validate (or invalidate) the idea before building
2. **Iterate through conversation** - Each prompt refined the architecture
3. **Let AI handle boilerplate** - Focus human creativity on strategy
4. **Debug together** - Build errors became learning moments

### On the Technical Journey

1. **Git add -f is your friend** - Check what's actually committed
2. **Demo mode is essential** - Let the app work without full infrastructure
3. **Type safety matters** - TypeScript caught many issues early
4. **Start with the schema** - Database design drives everything

### On Betting Systems

1. **Statistical significance is hard** - 56.8% sounds good but p=0.12 isn't conclusive
2. **The framework has value** - Even if one edge doesn't exist, the system can test others
3. **AI analysis adds context** - Numbers alone miss the narrative

---

## The Numbers

| Metric | Value |
|--------|-------|
| Lines of code written | ~3,500 |
| Files created | 35+ |
| Database records | 6,900+ |
| API endpoints | 10 |
| Deployment platforms | 3 |
| AI providers integrated | 2 |
| Time from idea to production | 1 session |
| Beers that sparked the idea | 3 |

---

## Closing Thoughts

What started as a tipsy observation at a bar became a fully-deployed betting analysis platform in a single Claude Code session. The journey from "I wonder if top teams cover more in conference games" to a live dashboard with AI-powered analysis demonstrates the power of conversational development.

The edge might not be statistically significant (yet), but the infrastructure to find and exploit edges is now in place. And that's the real win.

**The bar tab:** $47

**The Supabase bill:** $0 (free tier)

**The Vercel bill:** $0 (free tier)

**The Railway bill:** ~$5/month

**Having an AI-powered betting dashboard for March Madness:** Priceless

---

*Built with Claude Code, deployed with determination, inspired by bourbon.*
