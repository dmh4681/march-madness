"""
AI Bracket Pick Generator

Generates tournament bracket picks using Claude (or Grok) AI for all
NCAA Tournament games. Uses KenPom + Haslametrics data when available,
considers seed matchup history and single-elimination dynamics.

Usage:
    python -m backend.data_collection.bracket_pick_generator
    python -m backend.data_collection.bracket_pick_generator --season 2026 --round round_64
    python -m backend.data_collection.bracket_pick_generator --region East --force
    python -m backend.data_collection.bracket_pick_generator --provider grok --delay 3

Can also be triggered via API: POST /tournament/generate-picks
"""

import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime
from typing import Optional, Literal

from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

EASTERN_TZ = ZoneInfo("America/New_York")

# ============================================
# Seed Matchup Historical Win Rates
# ============================================

# Higher seed (lower number) historical win rates in NCAA Tournament (1985-2024)
SEED_MATCHUP_HISTORY = {
    (1, 16): 0.99,   # 1-seeds almost never lose (1 loss: UMBC over Virginia 2018)
    (2, 15): 0.94,   # 15-seeds win ~6% of the time
    (3, 14): 0.85,   # 14-seeds pull upsets occasionally
    (4, 13): 0.79,   # 13-seeds are a sneaky upset pick
    (5, 12): 0.65,   # Classic 5-12 upset — happens ~35% of the time
    (6, 11): 0.62,   # 11-seeds frequently upset (First Four teams can be dangerous)
    (7, 10): 0.61,   # Competitive matchup, slight edge to 7
    (8, 9):  0.52,   # Essentially a coin flip
}


def get_seed_matchup_context(home_seed: Optional[int], away_seed: Optional[int]) -> str:
    """
    Build seed matchup historical context string for the AI prompt.

    Returns a human-readable summary of how this seed matchup has historically
    played out in the NCAA Tournament.
    """
    if not home_seed or not away_seed:
        return "Seed data not available for historical comparison."

    higher_seed = min(home_seed, away_seed)
    lower_seed = max(home_seed, away_seed)

    # Look up in history table
    key = (higher_seed, lower_seed)
    if key in SEED_MATCHUP_HISTORY:
        win_rate = SEED_MATCHUP_HISTORY[key]
        upset_rate = 1 - win_rate
        higher_label = f"#{higher_seed} seed"
        lower_label = f"#{lower_seed} seed"

        context = f"Historical: {higher_label} beats {lower_label} {win_rate*100:.0f}% of the time."

        if upset_rate >= 0.30:
            context += f" This is a classic upset-prone matchup ({upset_rate*100:.0f}% upset rate)."
        elif upset_rate >= 0.15:
            context += f" Upsets happen but are uncommon ({upset_rate*100:.0f}% upset rate)."
        elif upset_rate >= 0.05:
            context += f" Upsets are rare ({upset_rate*100:.0f}% upset rate)."
        else:
            context += " Upsets are extremely rare at this seed line."

        return context

    # Same seed or non-standard matchup (later rounds)
    if home_seed == away_seed:
        return f"Both teams are #{home_seed} seeds — evenly matched on paper."

    seed_diff = abs(home_seed - away_seed)
    if seed_diff <= 2:
        return f"#{higher_seed} vs #{lower_seed} — closely matched seeds, expect a competitive game."
    elif seed_diff <= 5:
        return f"#{higher_seed} vs #{lower_seed} — moderate seed gap. The higher seed is favored but upsets occur."
    else:
        return f"#{higher_seed} vs #{lower_seed} — significant seed gap. The higher seed is heavily favored."


# ============================================
# Single Pick Generation
# ============================================

def _generate_single_pick(
    game: dict,
    tournament_id: str,
    provider: Literal["claude", "grok"],
) -> dict:
    """
    Generate a single bracket pick for one tournament game.

    1. Calls build_game_context(game_id) for full analytics
    2. Adds tournament-specific metadata (seeds, region, round)
    3. Builds tournament-specific prompt
    4. Calls Claude or Grok
    5. Maps AI response to team_id
    6. Stores via upsert_bracket_pick()

    Returns dict with pick result: game_id, picked_team, confidence, reasoning, status
    """
    try:
        from backend.api.ai_service import (
            build_game_context,
            build_tournament_pick_prompt,
            _extract_json_from_response,
            claude_client,
            grok_client,
        )
        from backend.api.supabase_client import (
            upsert_bracket_pick,
            get_game_by_id,
        )
    except ImportError:
        from ..api.ai_service import (
            build_game_context,
            build_tournament_pick_prompt,
            _extract_json_from_response,
            claude_client,
            grok_client,
        )
        from ..api.supabase_client import (
            upsert_bracket_pick,
            get_game_by_id,
        )

    import anthropic
    import hashlib

    game_id = game["game_id"]

    # 1. Build full game context (KenPom, Haslametrics, spreads, etc.)
    context = build_game_context(game_id)

    # 2. Build tournament-specific metadata
    matchup_metadata = {
        "home_seed": game.get("home_seed"),
        "away_seed": game.get("away_seed"),
        "home_region": game.get("home_region"),
        "away_region": game.get("away_region"),
        "tournament_round": game.get("tournament_round"),
        "seed_history": get_seed_matchup_context(
            game.get("home_seed"),
            game.get("away_seed"),
        ),
    }

    # 3. Build tournament-specific prompt
    prompt = build_tournament_pick_prompt(context, matchup_metadata)

    # 4. Call AI provider with retries
    response_text = None
    last_error = None

    for attempt in range(3):
        try:
            if provider == "claude":
                if not claude_client:
                    raise ValueError("Claude API key not configured")
                response = claude_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.content[0].text
            else:  # grok
                if not grok_client:
                    raise ValueError("Grok API key not configured")
                response = grok_client.chat.completions.create(
                    model="grok-3",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                )
                response_text = response.choices[0].message.content
            break
        except Exception as e:
            last_error = e
            logger.warning(f"AI API attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    if response_text is None:
        raise last_error or ValueError("AI call failed after 3 attempts")

    # 5. Parse AI response
    analysis = _extract_json_from_response(response_text)

    picked_side = analysis.get("picked_team", "").lower().strip()
    confidence = analysis.get("confidence_score", 0.5)
    key_factors = analysis.get("key_factors", [])
    reasoning = analysis.get("reasoning", "")

    # 6. Map "home"/"away" to team_id
    full_game = get_game_by_id(game_id)
    if not full_game:
        raise ValueError(f"Game {game_id} not found in database")

    picked_team_id = None
    picked_team_name = "unknown"

    if picked_side == "home":
        picked_team_id = full_game["home_team_id"]
        picked_team_name = context.get("home_team", "home")
    elif picked_side == "away":
        picked_team_id = full_game["away_team_id"]
        picked_team_name = context.get("away_team", "away")
    else:
        # Fallback: try to match by team name
        picked_name = analysis.get("picked_team", "")
        home_name = context.get("home_team", "")
        away_name = context.get("away_team", "")

        if picked_name and home_name and picked_name.lower() in home_name.lower():
            picked_team_id = full_game["home_team_id"]
            picked_team_name = home_name
            picked_side = "home"
        elif picked_name and away_name and picked_name.lower() in away_name.lower():
            picked_team_id = full_game["away_team_id"]
            picked_team_name = away_name
            picked_side = "away"
        else:
            # Last resort: pick the higher seed (lower number)
            home_seed = game.get("home_seed") or 99
            away_seed = game.get("away_seed") or 99
            if home_seed <= away_seed:
                picked_team_id = full_game["home_team_id"]
                picked_team_name = context.get("home_team", "home")
                picked_side = "home"
            else:
                picked_team_id = full_game["away_team_id"]
                picked_team_name = context.get("away_team", "away")
                picked_side = "away"
            logger.warning(
                f"AI returned '{analysis.get('picked_team')}' instead of home/away. "
                f"Defaulting to higher seed: {picked_team_name}"
            )

    # 7. Build reasoning string
    full_reasoning = reasoning
    if key_factors:
        factors_str = "; ".join(key_factors[:5])
        full_reasoning = f"{reasoning} | Key factors: {factors_str}"

    # 8. Upsert the bracket pick
    pick_data = {
        "tournament_id": tournament_id,
        "game_id": game_id,
        "round": game.get("tournament_round", "unknown"),
        "region": game.get("home_region") or game.get("away_region"),
        "picked_team_id": picked_team_id,
        "confidence_score": min(max(float(confidence), 0.0), 1.0),
        "reasoning": full_reasoning[:1000],
    }

    upsert_bracket_pick(pick_data)

    return {
        "game_id": game_id,
        "status": "success",
        "picked_team": picked_team_name,
        "picked_side": picked_side,
        "confidence": float(confidence),
        "reasoning": reasoning[:200],
        "key_factors": key_factors,
    }


# ============================================
# Main Orchestrator
# ============================================

def generate_bracket_picks(
    season: int,
    region: Optional[str] = None,
    tournament_round: Optional[str] = None,
    provider: Literal["claude", "grok"] = "claude",
    force_regenerate: bool = False,
    delay_seconds: float = 2.0,
) -> dict:
    """
    Generate AI bracket picks for tournament games.

    Fetches all tournament matchups, calls AI for each game that doesn't
    already have a pick, and stores results via upsert_bracket_pick().

    Args:
        season: Tournament year (e.g. 2026)
        region: Filter to specific region (East/West/South/Midwest)
        tournament_round: Filter to specific round (round_64, etc.)
        provider: AI provider ("claude" or "grok")
        force_regenerate: If True, overwrite existing picks
        delay_seconds: Pause between AI calls (rate limiting)

    Returns:
        Dict with: picks_generated, picks_skipped, errors, total_games, results
    """
    try:
        from backend.api.supabase_client import (
            get_tournament,
            get_tournament_bracket_view,
        )
    except ImportError:
        from ..api.supabase_client import (
            get_tournament,
            get_tournament_bracket_view,
        )

    print(f"\n{'='*60}")
    print(f"AI BRACKET PICK GENERATOR — {season}")
    print(f"Provider: {provider} | Force: {force_regenerate}")
    if region:
        print(f"Region filter: {region}")
    if tournament_round:
        print(f"Round filter: {tournament_round}")
    print(f"{'='*60}\n")

    # 1. Get tournament
    tournament = get_tournament(season)
    if not tournament:
        print(f"ERROR: No tournament found for {season}")
        return {"error": f"No tournament found for {season}", "total_games": 0}

    tournament_id = tournament["id"]
    print(f"Tournament: {tournament['name']} (status: {tournament['status']})")

    # 2. Fetch games from tournament_bracket view
    games = get_tournament_bracket_view(season, region=region, tournament_round=tournament_round)
    if not games:
        print("No tournament games found. Bracket may not be set yet.")
        return {
            "season": season,
            "status": "no_games_found",
            "total_games": 0,
            "picks_generated": 0,
            "picks_skipped": 0,
            "errors": 0,
        }

    print(f"Found {len(games)} tournament games")

    # 3. Filter: skip games with existing picks (unless force)
    games_to_pick = []
    picks_skipped = 0

    for game in games:
        if game.get("picked_team_id") and not force_regenerate:
            picks_skipped += 1
            continue
        # Skip games without two teams (TBD matchups in later rounds)
        if not game.get("home_team") or not game.get("away_team"):
            continue
        games_to_pick.append(game)

    print(f"Games to analyze: {len(games_to_pick)} (skipped {picks_skipped} with existing picks)\n")

    if not games_to_pick:
        print("All games already have picks. Use --force to regenerate.")
        return {
            "season": season,
            "provider": provider,
            "total_games": len(games),
            "picks_generated": 0,
            "picks_skipped": picks_skipped,
            "errors": 0,
            "results": [],
        }

    # 4. Generate picks sequentially with delay
    results = []
    picks_generated = 0
    errors = 0

    for i, game in enumerate(games_to_pick):
        round_display = (game.get("tournament_round") or "unknown").replace("_", " ").title()
        away_seed = game.get("away_seed", "?")
        home_seed = game.get("home_seed", "?")

        print(
            f"[{i+1}/{len(games_to_pick)}] {round_display}: "
            f"#{away_seed} {game.get('away_team', 'TBD')} vs "
            f"#{home_seed} {game.get('home_team', 'TBD')}"
        )

        try:
            result = _generate_single_pick(game, tournament_id, provider)
            results.append(result)

            if result["status"] == "success":
                picks_generated += 1
                conf = result["confidence"]
                print(f"  -> Picked: {result['picked_team']} (confidence: {conf:.0%})")
                if result.get("key_factors"):
                    print(f"     Factors: {', '.join(result['key_factors'][:3])}")
            else:
                errors += 1
                print(f"  -> ERROR: {result.get('error', 'unknown')}")

        except Exception as e:
            errors += 1
            results.append({
                "game_id": game.get("game_id"),
                "status": "error",
                "error": str(e)[:200],
            })
            logger.error(f"Pick generation failed: {e}")
            print(f"  -> EXCEPTION: {e}")

        # Rate limiting between AI calls
        if i < len(games_to_pick) - 1:
            time.sleep(delay_seconds)

    # Summary
    print(f"\n{'='*60}")
    print(f"BRACKET PICK GENERATION COMPLETE")
    print(f"  Generated: {picks_generated} picks")
    print(f"  Skipped: {picks_skipped} (existing)")
    print(f"  Errors: {errors}")
    print(f"  Total games: {len(games)}")
    print(f"{'='*60}\n")

    return {
        "season": season,
        "provider": provider,
        "total_games": len(games),
        "picks_generated": picks_generated,
        "picks_skipped": picks_skipped,
        "errors": errors,
        "results": results,
    }


# ============================================
# CLI Entry Point
# ============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate AI bracket picks for NCAA Tournament"
    )
    parser.add_argument(
        "--season", type=int, default=None,
        help="Tournament year (default: current)"
    )
    parser.add_argument(
        "--region", type=str, default=None,
        choices=["East", "West", "South", "Midwest"],
        help="Filter to a specific region"
    )
    parser.add_argument(
        "--round", type=str, default=None,
        choices=[
            "first_four", "round_64", "round_32",
            "sweet_16", "elite_8", "final_4", "championship",
        ],
        help="Filter to a specific round"
    )
    parser.add_argument(
        "--provider", type=str, default="claude",
        choices=["claude", "grok"],
        help="AI provider (default: claude)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate picks even if they already exist"
    )
    parser.add_argument(
        "--delay", type=float, default=2.0,
        help="Seconds between AI calls (default: 2.0)"
    )

    args = parser.parse_args()
    season = args.season or datetime.now(EASTERN_TZ).year

    results = generate_bracket_picks(
        season=season,
        region=args.region,
        tournament_round=args.round,
        provider=args.provider,
        force_regenerate=args.force,
        delay_seconds=args.delay,
    )

    print(f"\nResults: {json.dumps({k: v for k, v in results.items() if k != 'results'}, indent=2)}")
