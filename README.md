# Conference Contrarian

A data-driven system to identify and exploit a betting edge: **unranked teams vs ranked teams in the same conference tend to cover spreads at >52.4%** (the breakeven threshold for -110 odds).

## Project Philosophy

- **Validate the edge BEFORE building the product**
- Steal liberally from existing NCAA analytics projects
- Ship MVP fast, iterate based on real data
- Simple models beat complex ones (start with logistic regression)
- Track everything (every prediction, every result)

## Project Status

- [x] Research existing solutions
- [ ] Data collection (2014-2024)
- [ ] Edge validation
- [ ] Model development
- [ ] API deployment
- [ ] Frontend dashboard

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run data collection
python backend/data_collection/scraper.py --years 2014-2024

# Validate edge
python backend/analysis/validate_edge.py
```

## Project Structure

```
conference-contrarian/
├── RESEARCH.md              # Research findings and repo references
├── backend/
│   ├── data_collection/     # Scrapers for game data, rankings, odds
│   ├── analysis/            # Edge validation and backtesting
│   ├── models/              # ML models (logistic, XGBoost)
│   ├── api/                 # FastAPI endpoints
│   ├── notebooks/           # Jupyter exploration
│   └── data/                # Raw/processed data storage
├── frontend/                # Next.js dashboard (after validation)
└── scripts/                 # Setup and automation
```

## The Hypothesis

In NCAA basketball, when a **ranked team** plays an **unranked team** from the **same conference**, the unranked underdog covers the spread at a higher rate than expected.

**Why this might work:**
- Conference familiarity reduces skill gap
- Markets overvalue ranking prestige
- "Trap game" psychology

**Success criteria:**
- ATS% > 52.4% (breakeven at -110)
- P-value < 0.05
- Sample size > 500 games

## Data Sources

| Source | Data | Status |
|--------|------|--------|
| [CBBpy](https://github.com/dcstats/CBBpy) | Game scores, schedules | Primary |
| [College Poll Archive](https://collegepollarchive.com) | Historical AP rankings | To implement |
| [The Odds API](https://the-odds-api.com) | Historical spreads (2020+) | To implement |
| [Sports Reference](https://www.sports-reference.com/cbb/) | Backup game data | Fallback |

## Tech Stack

- **Data**: Python, pandas, SQLite
- **ML**: scikit-learn, XGBoost
- **API**: FastAPI
- **Frontend**: Next.js (planned)

## Documentation

- [RESEARCH.md](RESEARCH.md) - Detailed research findings and code patterns to steal

## Contributing

This is a personal project to validate a betting hypothesis. If the edge validates, contributions welcome!
