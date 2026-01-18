# Conference Contrarian

AI-powered college basketball betting analysis. Find edges, get recommendations, track performance.

![Status](https://img.shields.io/badge/status-live-brightgreen)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Claude](https://img.shields.io/badge/AI-Claude-orange)

## Features

- **Real-time Spreads** - Current betting lines from The Odds API
- **AI Analysis** - Claude-powered game breakdowns with betting recommendations
- **Confidence Tiers** - High/Medium/Low picks based on edge detection
- **Performance Tracking** - ROI, win rate, and streak tracking
- **March Madness Ready** - Tournament bracket view and analysis

## Screenshots

| Dashboard | Game Detail | AI Analysis |
|-----------|-------------|-------------|
| Today's games with spreads | Full matchup breakdown | Claude's betting recommendation |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11 |
| Database | Supabase (PostgreSQL) |
| AI | Claude API (Anthropic) |
| Hosting | Vercel (frontend), Railway (backend) |
| Data | The Odds API, CBBpy |

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- Supabase account
- Anthropic API key
- The Odds API key

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/march-madness.git
cd march-madness

# Frontend
cd frontend
npm install

# Backend
cd ../
pip install -r requirements.txt
```

### 2. Set Up Supabase

1. Create a new Supabase project
2. Run the migrations in `supabase/migrations/` via SQL Editor
3. Copy your project URL and keys

### 3. Configure Environment Variables

**Frontend** (`frontend/.env.local`):
```env
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Backend** (`.env`):
```env
SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_KEY=your-service-key
ANTHROPIC_API_KEY=your-claude-key
ODDS_API_KEY=your-odds-api-key
```

### 4. Run Locally

```bash
# Terminal 1 - Backend
uvicorn backend.api.main:app --reload

# Terminal 2 - Frontend
cd frontend && npm run dev
```

Visit `http://localhost:3000`

## Project Structure

```
march-madness/
├── frontend/               # Next.js application
│   ├── src/app/           # Pages (App Router)
│   ├── src/components/    # React components
│   └── src/lib/           # Utilities and types
├── backend/
│   ├── api/               # FastAPI endpoints
│   ├── data_collection/   # Scrapers and pipelines
│   └── models/            # ML prediction models
├── supabase/
│   └── migrations/        # Database schema
└── .github/workflows/     # CI/CD (daily refresh)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | API status |
| `/today` | GET | Today's games |
| `/games` | GET | Upcoming games |
| `/ai-analysis` | POST | Run Claude analysis |
| `/refresh` | POST | Trigger data refresh |

## Data Pipeline

The daily refresh pipeline runs at 6 AM EST via GitHub Actions:

1. Fetch current spreads from The Odds API
2. Update games in Supabase
3. Run predictions on upcoming games
4. Generate AI analysis for today's games

## Deployment

### Vercel (Frontend)

1. Import repo to Vercel
2. Set root directory to `frontend`
3. Add environment variables
4. Deploy

### Railway (Backend)

1. Import repo to Railway
2. Add environment variables
3. Deploy (uses `Procfile`)

## Configuration

### GitHub Actions Secrets

For the daily refresh cron job:

- `RAILWAY_API_URL` - Your Railway backend URL
- `REFRESH_API_KEY` - Optional auth key

## Database Schema

**Tables:**
- `teams` - NCAA teams and conferences
- `games` - Game schedules and scores
- `spreads` - Betting lines
- `rankings` - AP poll rankings
- `predictions` - Model predictions
- `ai_analysis` - Claude analysis results
- `bet_results` - Outcome tracking

## Roadmap

- [x] Dashboard with real-time spreads
- [x] AI analysis with Claude
- [x] Daily data refresh pipeline
- [x] Performance tracking page
- [x] March Madness bracket view
- [ ] User authentication
- [ ] Stripe subscription
- [ ] Email notifications
- [ ] Mobile app

## License

Private project. All rights reserved.

## Acknowledgments

- [CBBpy](https://github.com/dcstats/CBBpy) - NCAA basketball data
- [The Odds API](https://the-odds-api.com) - Betting lines
- [Supabase](https://supabase.com) - Database and auth
- [Claude](https://anthropic.com) - AI analysis

---

Built with Claude Code. For entertainment purposes only. Please gamble responsibly.
