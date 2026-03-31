# Tournament Feature: Setup & Deployment Guide

This document covers how to stand up the NCAA Tournament bracket feature end-to-end — database migrations, backend deployment on Railway, frontend deployment on Vercel, and the operational workflows that run each year around Selection Sunday.

---

## Table of Contents

1. [Feature Overview](#feature-overview)
2. [Database Setup](#database-setup)
3. [Environment Variables](#environment-variables)
4. [Backend Deployment (Railway)](#backend-deployment-railway)
5. [Frontend Deployment (Vercel)](#frontend-deployment-vercel)
6. [Operational Workflows](#operational-workflows)
7. [API Reference](#api-reference)
8. [Data Pipeline](#data-pipeline)
9. [Troubleshooting](#troubleshooting)

---

## Feature Overview

The tournament feature adds three capabilities on top of the core Conference Contrarian app:

| Capability | Where it lives |
|------------|---------------|
| Bracket seeding (68 teams → regions/seeds) | `tournament_seeds` table, `/tournament/set-bracket` endpoint, `bracket_scraper.py` |
| AI bracket picks per game | `bracket_picks` table, `/tournament/generate-picks` endpoint, `bracket_pick_generator.py` |
| Frontend bracket view | `frontend/src/app/march-madness/` |

The feature re-uses existing `games`, `teams`, `spreads`, `kenpom_ratings`, and `haslametrics_ratings` tables — no duplicate data storage.

---

## Database Setup

### Prerequisites

- Supabase project running with the core schema already applied (migrations `20250118000000` through `20250121000000`)
- The `update_updated_at()` trigger function must already exist (created in the initial migration)

### Run the migrations in order

Open the Supabase SQL editor (or run via `supabase db push` if using the CLI) and apply the following files in sequence:

```
supabase/migrations/20260301000000_tournament_bracket.sql
supabase/migrations/20260310000000_bracket_query_optimization.sql
```

**What each migration creates:**

`20260301000000_tournament_bracket.sql`
- `tournaments` table — one row per season, tracks status and champion
- `tournament_seeds` table — 64-68 teams per tournament with seed/region/play-in info
- `bracket_picks` table — one AI pick per tournament game, with grading result
- `tournament_bracket` view — tournament games joined with seeds, spreads, and picks
- `tournament_region_summary` view — seeds grouped by region with `is_alive` flag
- 7 indexes on the new tables

`20260310000000_bracket_query_optimization.sql`
- 5 covering indexes that eliminate heap fetches in the view queries
- 2 partial indexes (alive teams, ungraded picks) for the grading pipeline
- Rewrites `tournament_bracket` view to use a direct JOIN instead of a correlated subquery

### Verify the migration

```sql
-- Should return the three new tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('tournaments', 'tournament_seeds', 'bracket_picks');

-- Should return the two new views
SELECT table_name FROM information_schema.views
WHERE table_schema = 'public'
  AND table_name IN ('tournament_bracket', 'tournament_region_summary');
```

### Schema summary

**`tournaments`**

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `season` | integer | Unique. Year of the tournament (e.g. 2026) |
| `status` | text | `upcoming` → `bracket_set` → `in_progress` → `completed` |
| `selection_sunday_date` | date | |
| `start_date` | date | First Four tip-off date |
| `end_date` | date | Championship game date |
| `champion_team_id` | UUID | FK to `teams`, set after the final |

**`tournament_seeds`**

| Column | Type | Notes |
|--------|------|-------|
| `tournament_id` | UUID | FK to `tournaments` |
| `team_id` | UUID | FK to `teams` |
| `seed` | integer | 1–16 within the region |
| `region` | text | `East`, `West`, `South`, `Midwest` |
| `is_play_in` | boolean | `true` for First Four teams sharing a seed slot |
| `play_in_matchup` | integer | `1` or `2` for play-in pairs, `NULL` otherwise |
| `eliminated_in_round` | text | Set by grading; `NULL` while alive or champion |

**`bracket_picks`**

| Column | Type | Notes |
|--------|------|-------|
| `tournament_id` | UUID | FK to `tournaments` |
| `game_id` | UUID | FK to `games` |
| `round` | text | `first_four`, `round_64`, `round_32`, `sweet_16`, `elite_8`, `final_4`, `championship` |
| `region` | text | `NULL` for Final Four and Championship |
| `picked_team_id` | UUID | FK to `teams` |
| `confidence_score` | decimal | 0.00–1.00 |
| `reasoning` | text | AI explanation |
| `is_correct` | boolean | `NULL` until graded |

---

## Environment Variables

No new environment variables are required for the tournament feature. The existing set covers everything:

### Railway (backend)

```
SUPABASE_URL=https://<project-id>.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>
ANTHROPIC_API_KEY=<claude-api-key>
GROK_API_KEY=<grok-api-key>          # optional, for Grok picks
ALLOWED_ORIGINS=https://confcontrarian.com,https://www.confcontrarian.com
```

KenPom and Haslametrics credentials are used for generating richer AI picks but are not required — the pick generator degrades gracefully when analytics data is absent.

### Vercel (frontend)

```
NEXT_PUBLIC_SUPABASE_URL=https://<project-id>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
NEXT_PUBLIC_API_URL=https://web-production-e5efb.up.railway.app
```

`NEXT_PUBLIC_API_URL` must include `https://`.

---

## Backend Deployment (Railway)

The tournament endpoints are part of `backend/api/main.py` — no separate service is needed. Deploying the backend automatically includes them.

### Deploy

```bash
git push origin main   # Railway auto-deploys on push to main
```

### Verify the endpoints are live

```bash
# Health check
curl https://web-production-e5efb.up.railway.app/health

# Tournament metadata endpoint (creates a row for 2026 if none exists)
curl "https://web-production-e5efb.up.railway.app/tournament/2026"
```

Expected response for a fresh season:

```json
{
  "id": "<uuid>",
  "season": 2026,
  "name": "NCAA Tournament",
  "status": "upcoming",
  "team_count": 0,
  "game_count": 0,
  "picks_count": 0
}
```

### Railway configuration reference

`Procfile`:
```
web: uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT
```

`railway.json`:
```json
{
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

`runtime.txt`: Python 3.11.7

---

## Frontend Deployment (Vercel)

The bracket page lives at `/march-madness` and is part of the existing Next.js app — no separate deployment.

```bash
git push origin main   # Vercel auto-deploys on push
```

### Verify the page

Navigate to `https://confcontrarian.com/march-madness`. Before seeding, the page shows an empty state with tournament status `upcoming`.

### Frontend files

| File | Purpose |
|------|---------|
| `frontend/src/app/march-madness/page.tsx` | Server component — fetches tournament data from Supabase |
| `frontend/src/app/march-madness/BracketView.tsx` | Client component — region tabs, matchup rows, game links |
| `frontend/src/app/march-madness/BracketErrorBoundary.tsx` | Error fallback UI |
| `frontend/src/app/march-madness/loading.tsx` | Skeleton loading state |

---

## Operational Workflows

### Selection Sunday — seeding the bracket

Run after the bracket is announced (typically the Sunday before the tournament starts, mid-March).

**Option A: Automated scraper (ESPN)**

```bash
# From the repo root, targeting Railway's Python environment locally:
python -m backend.data_collection.bracket_scraper --season 2026
```

The scraper calls the ESPN public API, parses seeds/regions from `competitors[].curatedRank.current` and note headlines, then calls `POST /tournament/set-bracket` to populate `tournament_seeds`.

**Option B: Manual API call**

```bash
curl -X POST https://web-production-e5efb.up.railway.app/tournament/set-bracket \
  -H "Content-Type: application/json" \
  -d '{
    "season": 2026,
    "seeds": [
      {"team_name": "Duke", "seed": 1, "region": "East"},
      {"team_name": "Kansas", "seed": 1, "region": "West"},
      ...
    ]
  }'
```

Requirements:
- Exactly 64–68 entries (include First Four teams with `"is_play_in": true` and `"play_in_matchup": 1` or `2`)
- `team_name` must match the `name` column in the `teams` table (case-insensitive search is used internally)
- `seed` must be 1–16
- `region` must be one of: `East`, `West`, `South`, `Midwest`

After a successful call, `GET /tournament/2026` will show `"status": "bracket_set"` and `"team_count": 68`.

### Generating AI bracket picks

Run after seeding, before games tip off. The pick generator uses KenPom + Haslametrics data and seed matchup history to have Claude (or Grok) pick every game.

**Via API (runs as background job):**

```bash
# All games, all regions — Claude
curl -X POST https://web-production-e5efb.up.railway.app/tournament/generate-picks \
  -H "Content-Type: application/json" \
  -d '{"season": 2026, "provider": "claude"}'

# Specific region only
curl -X POST https://web-production-e5efb.up.railway.app/tournament/generate-picks \
  -H "Content-Type: application/json" \
  -d '{"season": 2026, "region": "East", "provider": "claude"}'

# Overwrite existing picks (force)
curl -X POST https://web-production-e5efb.up.railway.app/tournament/generate-picks \
  -H "Content-Type: application/json" \
  -d '{"season": 2026, "provider": "claude", "force": true}'
```

The endpoint returns a `job_id` immediately. Poll for completion:

```bash
curl "https://web-production-e5efb.up.railway.app/api/v1/batch-analyze/<job_id>"
```

**Via CLI (local):**

```bash
python -m backend.data_collection.bracket_pick_generator --season 2026
python -m backend.data_collection.bracket_pick_generator --season 2026 --round round_64
python -m backend.data_collection.bracket_pick_generator --region East --force
python -m backend.data_collection.bracket_pick_generator --provider grok --delay 3
```

CLI flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--season` | current year | Tournament season |
| `--region` | all regions | Restrict to one region |
| `--round` | all rounds | Restrict to one round |
| `--provider` | `claude` | `claude` or `grok` |
| `--force` | false | Overwrite existing picks |
| `--delay` | 1 | Seconds between AI API calls |

### Grading picks after games complete

Run after each day's games finish (or after each round).

```bash
curl -X POST "https://web-production-e5efb.up.railway.app/tournament/grade?season=2026"
```

This endpoint:
1. Finds all `bracket_picks` where `is_correct IS NULL` and the linked `game` has a final score
2. Compares `picked_team_id` against the actual winning team
3. Sets `is_correct = true/false` on the pick
4. Sets `eliminated_in_round` on the losing team in `tournament_seeds`

Run it as many times as you like — it is idempotent for already-graded picks.

### Updating tournament status

The status field on `tournaments` drives UI copy on the bracket page. Update it manually as the tournament progresses:

```sql
-- After bracket set:   already done by set-bracket endpoint
-- When games begin:
UPDATE tournaments SET status = 'in_progress' WHERE season = 2026;

-- After the championship game:
UPDATE tournaments
SET status = 'completed',
    champion_team_id = (SELECT id FROM teams WHERE name = 'Duke')
WHERE season = 2026;
```

---

## API Reference

All tournament endpoints are under `/tournament/`. Full validation is enforced on every endpoint (UUID format, region/round whitelists, team name regex).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/tournament/{season}` | Tournament metadata with counts. Creates a row for the season if none exists. |
| `GET` | `/tournament/bracket` | All tournament games with seeds, spreads, and picks. Query params: `season`, `region`, `round`. |
| `GET` | `/tournament/regions` | Seeds grouped by region for a season. Query param: `season`. |
| `POST` | `/tournament/set-bracket` | Batch-populate `tournament_seeds` for a season. Body: `{season, seeds[]}`. |
| `POST` | `/tournament/pick` | Insert or update a single bracket pick. Body: `{game_id, picked_team_id, confidence_score?, reasoning?}`. |
| `POST` | `/tournament/generate-picks` | Kick off AI pick generation as a background job. Returns `{job_id}`. |
| `POST` | `/tournament/grade` | Grade picks for all completed games. Query param: `season`. |
| `POST` | `/tournament/ai-analysis` | Run tournament-specific AI analysis on a single game. Body: `{game_id, provider?}`. |
| `GET` | `/tournament/ai-analysis` | Debug view of AI analysis records for tournament games. |

### Input validation rules

- **Region**: must be one of `East`, `West`, `South`, `Midwest`
- **Round**: must be one of `first_four`, `round_64`, `round_32`, `sweet_16`, `elite_8`, `final_4`, `championship`
- **UUIDs**: validated with regex `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
- **Team names**: validated with regex `^[a-zA-Z0-9\s\-\.\'\&\(\)]+$`
- **Season**: integer 2000–2100

---

## Data Pipeline

### How tournament games enter the `games` table

The `bracket_scraper.py` script marks existing games as tournament games by setting `is_tournament = true` and `tournament_round` on the `games` table. It does not create new game rows — those come from the existing daily refresh pipeline via The Odds API / CBBpy.

If tournament games aren't appearing in the bracket view, run the daily refresh first, then re-run the bracket scraper:

```bash
curl -X POST https://web-production-e5efb.up.railway.app/refresh
# wait for completion, then:
python -m backend.data_collection.bracket_scraper --season 2026
```

### AI pick prompt context

The pick generator (`bracket_pick_generator.py`) builds each prompt with:

1. **Seed matchup history** — hardcoded historical win rates (1985–2024) for all 8 first-round matchup types (1 vs 16 through 8 vs 9)
2. **KenPom data** — AdjO, AdjD, AdjEM, Tempo, SOS, Luck (when available)
3. **Haslametrics data** — All-Play %, Momentum, Efficiency, Quadrant records (always available, FREE)
4. **Single-elimination framing** — prompt explicitly asks AI to account for variance and game-day factors

### GitHub Actions daily refresh

`.github/workflows/daily-refresh.yml` runs at 6 AM EST. It calls `/refresh` on Railway, which runs all scrapers but **does not** run the bracket scraper or generate picks — those are manual/one-time operations per season.

To add bracket scraping to the daily refresh, add a step to the workflow that calls the `/refresh` endpoint after the standard refresh, or calls `bracket_scraper.py` directly via SSH into Railway.

---

## Troubleshooting

### `/tournament/set-bracket` returns 422 — team not found

The endpoint resolves team names against the `teams` table. If a name doesn't match, it logs a warning and continues (other teams still get seeded). Check Railway logs for `"Could not find team:"` lines.

Fix: run the following query in Supabase to find the correct name:

```sql
SELECT name FROM teams
WHERE name ILIKE '%<partial name>%'
ORDER BY name;
```

Then resubmit the seed entry with the exact name from the database.

### Bracket page shows no data

1. Check that `NEXT_PUBLIC_API_URL` includes `https://` in Vercel environment variables.
2. Check that the `tournament_bracket` view returns rows: `SELECT count(*) FROM tournament_bracket WHERE season = 2026;`
3. Check Railway logs for errors from `GET /tournament/bracket`.

### `generate-picks` job completes but picks are missing

1. Check that `tournament_seeds` has rows for the season: `SELECT count(*) FROM tournament_seeds ts JOIN tournaments t ON ts.tournament_id = t.id WHERE t.season = 2026;`
2. Check that the linked games have `is_tournament = true`.
3. Re-run with `"force": true` to overwrite any partially-written picks.

### `grade` endpoint leaves picks ungraded

Grading requires the game row to have a final score (`home_score IS NOT NULL`). If games are not yet scored, the picks correctly remain `NULL`. Re-run grading after scores are populated by the daily refresh.

### Bracket view is slow (>2s query time)

Verify the optimization migration ran. Check index existence:

```sql
SELECT indexname FROM pg_indexes
WHERE tablename IN ('tournament_seeds', 'bracket_picks', 'tournaments')
ORDER BY tablename, indexname;
```

You should see `idx_tournaments_season`, `idx_tournament_seeds_tid_team_covering`, `idx_bracket_picks_game_covering`, and the two partial indexes. If any are missing, re-apply `20260310000000_bracket_query_optimization.sql`.
