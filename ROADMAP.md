# Conference Contrarian Roadmap

> Last updated: 2026-02-22

## Mission

Conference Contrarian turns college basketball data into betting intelligence. It combines KenPom analytics, Haslametrics ratings, prediction market odds, and dual AI analysis (Claude + Grok) to find edges that sportsbooks miss — especially in conference play where familiarity breeds inefficiency.

## Current Phase: Tournament Preparation

The regular season product is live at confcontrarian.com with a working daily pipeline, AI analysis, and a performance dashboard. **March Madness 2026 starts March 20 — 26 days away.** Selection Sunday is March 16. Everything between now and then should serve one goal: being ready when the bracket drops.

## Active Goals

### 1. Build Tournament Bracket Data Model
**Priority: Critical — Deadline: March 15**
The bracket page (`/march-madness`) has a polished UI shell with correct 2026 dates and region tabs. It needs the data layer:
- Create bracket schema (regions, seeds, matchups, rounds) in Supabase
- Build API endpoints for bracket CRUD and round advancement
- Wire bracket data into the existing frontend shell
- Add Selection Sunday ingestion script (manual or API-based bracket import)

### 2. Tournament-Aware AI Analysis
**Priority: Critical — Deadline: March 15**
The AI analysis prompts are optimized for regular season games. Tournament context is different:
- Add tournament-specific prompt context (seed matchup history, one-and-done pressure, neutral court dynamics, conference tournament momentum)
- Include historical upset rates by seed differential
- Adjust confidence scoring for tournament volatility
- Add "bracket buster" detection for high-upset-probability games

### 3. Bracket Visualization & Picks Export
**Priority: High — Deadline: March 18**
The bracket page TODO already references `react-zoom-pan-pinch`. Build it:
- Interactive bracket visualization with per-matchup AI confidence
- Print-friendly / screenshot-friendly bracket export
- "My picks" mode where users can fill out their bracket with AI assistance
- Round-by-round progression tracking once games start

### 4. Tournament Performance Tracking
**Priority: High — By March 20**
Regular season performance data exists in `bet_results` and `season_performance`. Add tournament-specific tracking:
- Separate tournament pick accuracy from regular season stats
- Round-by-round performance breakdown
- "If you'd bet every AI pick" ROI calculator for the tournament
- Daily tournament summary in the performance dashboard

### 5. Regular Season Performance Hardening
**Priority: Medium — Ongoing**
Close the feedback loop on the daily picks:
- Ensure `bet_results` is being populated consistently from game outcomes
- Surface win rate, ROI, and edge accuracy prominently on the performance page
- Add confidence-calibration analysis (are 80%+ confidence picks actually hitting 80%?)

## Deferred / Not Now

- **User authentication** — No accounts needed for tournament. Public access is fine.
- **Stripe paywall** — Prove the picks work first. Monetize after the tournament.
- **Mobile app** — The web app is mobile-responsive. No native app needed.
- **Redis job queue** — The daily cron pipeline runs fine. No need for async jobs at this scale.
- **API versioning** — Single frontend client. No versioning needed.
- **Database connection pooling** — Supabase handles this. Not a bottleneck.
- **Frontend component tests (Jest)** — Ship tournament features first, test later.
- **KenPom/Haslametrics test utilities** — The scrapers work. Don't gold-plate them before the tournament.

## Completed Milestones

- [x] Full daily data pipeline (Odds API, KenPom, Haslametrics, prediction markets)
- [x] Dual AI analysis (Claude + Grok with analytics context)
- [x] Production deployment (Vercel + Railway + Supabase)
- [x] GameCard, GamesTable, AIAnalysis, ConfidenceBadge components
- [x] Prediction market integration (Polymarket + Kalshi) with arbitrage detection
- [x] Performance dashboard wired to real Supabase data
- [x] Security hardening (CSP, CORS, input validation, rate limiting)
- [x] 188+ backend tests across AI, data collection, and betting utilities
- [x] Batch AI analysis endpoint for multi-game processing
- [x] GitHub Actions daily cron (6 AM EST pipeline refresh)
- [x] March Madness page UI shell with 2026 dates and region tabs
- [x] Lazy loading and performance optimization
