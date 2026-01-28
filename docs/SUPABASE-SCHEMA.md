# Supabase Schema: College Basketball Analytics (Domain 1)

**Database:** sovereignty-path (`qxnxyvkilbksfilxlgai`)
**Last updated:** 2026-01-27

This domain owns all college basketball data: teams, games, betting spreads, predictions, ratings, and edge-detection tables.

---

## Table Overview

| Table | Rows | Status | Description |
|-------|------|--------|-------------|
| teams | 416 | Active | Hub table. All NCAA teams. |
| games | 6,590 | Active | Hub table. Game schedule and results. |
| spreads | 513 | Active | Betting lines per game. |
| predictions | 199 | Active | Model predictions per game. |
| ai_analysis | 216 | Active | LLM-generated game analysis. |
| prediction_markets | 670 | Active | Market odds per team/game. |
| prediction_market_prices | 0 | Unused | Historical price snapshots for markets. |
| arbitrage_opportunities | 0 | Unused | Detected arb between markets. |
| bet_results | 0 | Unused | Outcome tracking for placed bets. |
| rankings | 125 | Active | Weekly team rankings (AP, NET, etc). |
| kenpom_ratings | 1,296 | Active | KenPom advanced ratings per team. |
| haslametrics_ratings | 867 | Active | Haslametrics ratings per team. |
| performance_summary | 0 | Unused | Aggregated model performance stats. |
| edge_prediction_markets | 41 | Active | Edge-detected market opportunities. |
| edge_market_outcomes | 41 | Active | Resolved edge market results. |
| edge_scans | 22 | Active | Edge scanner run history. |
| edge_discovery_runs | 13 | Active | Discovery pipeline runs. |
| alert_rules | 3 | Active | User-defined alert conditions. |
| alert_history | 0 | Unused | Fired alert log. |
| alert_channel_config | 0 | Unused | Notification channel settings. |
| alert_subscriptions | 0 | Unused | User alert subscriptions. |

**Total: 21 tables (13 active, 8 unused/planned)**

---

## Hub Tables

### teams
The universal anchor for all basketball entities.

| Column (key) | Type | Notes |
|--------------|------|-------|
| id | uuid / int | PK |
| name | text | Team name |
| conference | text | Conference affiliation |
| season | int | Season year |

Referenced by: games, rankings, kenpom_ratings, haslametrics_ratings, prediction_markets

### games
Every scheduled and completed game.

| Column (key) | Type | Notes |
|--------------|------|-------|
| id | uuid / int | PK |
| home_team_id | FK → teams | |
| away_team_id | FK → teams | |
| game_date | date | |
| home_score | int | NULL if not yet played |
| away_score | int | NULL if not yet played |
| season | int | |

Referenced by: spreads, predictions, ai_analysis, prediction_markets, arbitrage_opportunities, bet_results

---

## Foreign Key Relationships

```
teams ─────────────────────────────────────────────────┐
  │                                                     │
  ├──< games.home_team_id                               │
  ├──< games.away_team_id                               │
  ├──< rankings.team_id                                 │
  ├──< kenpom_ratings.team_id                           │
  ├──< haslametrics_ratings.team_id                     │
  └──< prediction_markets.team_id                       │
                                                        │
games ──────────────────────────────────────────────────┤
  ├──< spreads.game_id                                  │
  ├──< predictions.game_id                              │
  ├──< ai_analysis.game_id                              │
  ├──< prediction_markets.game_id                       │
  ├──< arbitrage_opportunities.game_id                  │
  └──< bet_results.game_id                              │
                                                        │
predictions ────────────────────────────────────────────┤
  └──< bet_results.prediction_id                        │
                                                        │
prediction_markets ─────────────────────────────────────┤
  ├──< prediction_market_prices.prediction_market_id    │
  └──< arbitrage_opportunities.prediction_market_id     │
                                                        │
edge_prediction_markets ────────────────────────────────┤
  └──< edge_market_outcomes.edge_prediction_market_id   │
                                                        │
edge_market_outcomes ───────────────────────────────────┘
  └──< edge_scans.edge_market_outcome_id
```

---

## RLS Policies

| Access Level | Tables |
|-------------|--------|
| **Public read (anon)** | games, teams, spreads, predictions, rankings, kenpom_ratings, haslametrics_ratings, ai_analysis |
| **Anon read / service write** | edge_prediction_markets, edge_market_outcomes, edge_scans, edge_discovery_runs |
| **Service-role only** | alert_rules, alert_history, alert_channel_config, alert_subscriptions |
| **Service-role write (all)** | All tables require service-role for INSERT/UPDATE/DELETE |

---

## Unused / Planned Tables

These tables exist in the schema but have 0 rows. They represent planned features:

- **prediction_market_prices** - Price history tracking for prediction markets
- **arbitrage_opportunities** - Cross-market arbitrage detection
- **bet_results** - Bet outcome tracking and P&L
- **performance_summary** - Model accuracy aggregation
- **alert_history / alert_channel_config / alert_subscriptions** - Alert system (rules exist, but no alerts have fired yet)
