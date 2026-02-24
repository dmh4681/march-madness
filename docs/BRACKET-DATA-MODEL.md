# Tournament Bracket Data Model

## Overview

This document defines the data model for NCAA Tournament bracket functionality. The bracket system needs to support Selection Sunday ingestion, round-by-round progression, upset probability calculations, and user bracket picks.

**Target Deadline:** March 15, 2026 (before Selection Sunday)

## Existing Foundation

The `games` table already supports tournament flags:

```sql
-- Existing columns in games table
is_tournament    boolean     -- Flags tournament games
tournament_round text        -- "Round of 64", "Round of 32", "Sweet 16", etc.
```

## Proposed Schema

### `tournament_brackets` — One row per tournament year

```sql
CREATE TABLE tournament_brackets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    year            integer NOT NULL UNIQUE,
    selection_date  date NOT NULL,
    status          text NOT NULL DEFAULT 'pending',  -- pending, active, completed
    champion_team_id uuid REFERENCES teams(id),
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);
```

### `bracket_seeds` — 68 teams seeded into regions

```sql
CREATE TABLE bracket_seeds (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bracket_id      uuid NOT NULL REFERENCES tournament_brackets(id),
    team_id         uuid NOT NULL REFERENCES teams(id),
    seed            integer NOT NULL CHECK (seed BETWEEN 1 AND 16),
    region          text NOT NULL,  -- 'East', 'West', 'South', 'Midwest'
    play_in         boolean DEFAULT false,
    kenpom_rank     integer,
    kenpom_adj_em   float,
    has_adj_o       float,
    has_adj_d       float,
    created_at      timestamptz DEFAULT now(),
    UNIQUE(bracket_id, team_id)
);
```

### `bracket_matchups` — Each game slot in the bracket

```sql
CREATE TABLE bracket_matchups (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bracket_id      uuid NOT NULL REFERENCES tournament_brackets(id),
    round           integer NOT NULL,  -- 1=R64, 2=R32, 3=S16, 4=E8, 5=F4, 6=Championship
    round_name      text NOT NULL,     -- "Round of 64", "Sweet 16", etc.
    region          text,              -- NULL for Final Four and Championship
    matchup_number  integer NOT NULL,  -- Position within the round (1-32 for R64)

    -- Teams (populated as bracket advances)
    higher_seed_id  uuid REFERENCES bracket_seeds(id),
    lower_seed_id   uuid REFERENCES bracket_seeds(id),

    -- Result
    game_id         uuid REFERENCES games(id),  -- Links to actual game when played
    winner_seed_id  uuid REFERENCES bracket_seeds(id),
    is_upset        boolean,

    -- AI Analysis
    upset_probability float,  -- 0-100, Claude/Grok predicted upset chance
    ai_pick_seed_id   uuid REFERENCES bracket_seeds(id),
    ai_confidence      float,

    -- Timing
    scheduled_date  date,
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),

    UNIQUE(bracket_id, round, matchup_number)
);
```

### `historical_seed_performance` — Seed matchup history

```sql
CREATE TABLE historical_seed_performance (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    higher_seed     integer NOT NULL CHECK (higher_seed BETWEEN 1 AND 16),
    lower_seed      integer NOT NULL CHECK (lower_seed BETWEEN 1 AND 16),
    round           integer NOT NULL,
    total_matchups  integer NOT NULL DEFAULT 0,
    higher_seed_wins integer NOT NULL DEFAULT 0,
    lower_seed_wins integer NOT NULL DEFAULT 0,
    last_updated    timestamptz DEFAULT now(),
    UNIQUE(higher_seed, lower_seed, round)
);
```

## Round Constants

| Round | Number | Name | Games |
|-------|--------|------|-------|
| 1 | 1 | Round of 64 (First Round) | 32 |
| 2 | 2 | Round of 32 (Second Round) | 16 |
| 3 | 3 | Sweet 16 | 8 |
| 4 | 4 | Elite 8 | 4 |
| 5 | 5 | Final Four | 2 |
| 6 | 6 | Championship | 1 |

## Regions

Standard 4 regions: `East`, `West`, `South`, `Midwest`
Region names change yearly based on host city — store the canonical name.

## Data Flow

### Selection Sunday Ingestion

1. Teams and seeds are announced → populate `bracket_seeds` (68 entries)
2. Generate `bracket_matchups` for Round of 64 (32 matchups based on seeding)
3. Subsequent round matchups are created with NULL team references (filled as games complete)

### During Tournament

1. As games finish, update `bracket_matchups.winner_seed_id` and `game_id`
2. Populate next round's `higher_seed_id` / `lower_seed_id` from winners
3. Flag upsets (`is_upset = true` when lower seed wins)

### AI Analysis

For each matchup, the AI service can:
1. Pull `bracket_seeds` data (seed, KenPom rank, Haslametrics metrics)
2. Query `historical_seed_performance` for seed matchup trends
3. Generate `upset_probability` and `ai_pick_seed_id`
4. Store analysis in existing `ai_analysis` table with `is_tournament = true`

## API Endpoints (Planned)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/bracket/{year}` | Full bracket with all matchups |
| GET | `/bracket/{year}/region/{region}` | Single region bracket |
| POST | `/bracket/{year}/seed` | Ingest Selection Sunday data |
| POST | `/bracket/{year}/advance` | Record game result, advance winner |
| GET | `/bracket/{year}/upsets` | Upset probability analysis |
| GET | `/seed-trends/{higher}/{lower}` | Historical seed matchup data |

## Frontend Integration

The bracket page (`frontend/src/app/march-madness/page.tsx`) will consume these endpoints. The existing TODO references `react-zoom-pan-pinch` for mobile bracket navigation. Key components to build:

- `BracketRegion.tsx` — Single region tree (8→4→2→1)
- `MatchupCard.tsx` — Team pair with seed, score, upset probability
- `SeedBadge.tsx` — Seed number with historical win rate color coding
- `BracketTree.tsx` — Full bracket (4 regions → Final Four → Championship)
