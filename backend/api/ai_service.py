"""
AI Service for game analysis using Claude and Grok.

Provides betting analysis and recommendations using LLMs.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Optional, Literal

from dotenv import load_dotenv
import anthropic
from openai import OpenAI

from .supabase_client import (
    get_game_by_id,
    get_latest_spread,
    get_team_ranking,
    get_team_kenpom,
    insert_ai_analysis,
)

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = "https://api.x.ai/v1"  # Grok uses OpenAI-compatible API

# Initialize clients
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
grok_client = OpenAI(api_key=GROK_API_KEY, base_url=GROK_BASE_URL) if GROK_API_KEY else None

AIProvider = Literal["claude", "grok"]


def build_game_context(game_id: str) -> dict:
    """Build context object for AI analysis."""
    game = get_game_by_id(game_id)
    if not game:
        raise ValueError(f"Game not found: {game_id}")

    spread = get_latest_spread(game_id)

    # Get rankings
    home_ranking = None
    away_ranking = None
    if game.get("home_team_id"):
        home_ranking = get_team_ranking(game["home_team_id"], game["season"])
    if game.get("away_team_id"):
        away_ranking = get_team_ranking(game["away_team_id"], game["season"])

    # Get KenPom ratings
    home_kenpom = None
    away_kenpom = None
    if game.get("home_team_id"):
        home_kenpom = get_team_kenpom(game["home_team_id"], game["season"])
    if game.get("away_team_id"):
        away_kenpom = get_team_kenpom(game["away_team_id"], game["season"])

    return {
        "game_id": game_id,
        "date": game.get("date"),
        "home_team": game.get("home_team", {}).get("name", "Unknown"),
        "away_team": game.get("away_team", {}).get("name", "Unknown"),
        "home_conference": game.get("home_team", {}).get("conference"),
        "away_conference": game.get("away_team", {}).get("conference"),
        "home_rank": home_ranking.get("rank") if home_ranking else None,
        "away_rank": away_ranking.get("rank") if away_ranking else None,
        "is_conference_game": game.get("is_conference_game", False),
        "is_tournament": game.get("is_tournament", False),
        "venue": game.get("venue"),
        "neutral_site": game.get("neutral_site", False),
        "spread": spread.get("home_spread") if spread else None,
        "home_ml": spread.get("home_ml") if spread else None,
        "away_ml": spread.get("away_ml") if spread else None,
        "total": spread.get("over_under") if spread else None,
        # KenPom data
        "home_kenpom": home_kenpom,
        "away_kenpom": away_kenpom,
    }


def build_analysis_prompt(context: dict) -> str:
    """Build the analysis prompt for the AI."""
    home_rank_str = f"#{context['home_rank']}" if context["home_rank"] else "Unranked"
    away_rank_str = f"#{context['away_rank']}" if context["away_rank"] else "Unranked"

    spread_str = ""
    if context["spread"] is not None:
        spread_val = context["spread"]
        if spread_val < 0:
            spread_str = f"{context['home_team']} -{abs(spread_val)}"
        else:
            spread_str = f"{context['away_team']} -{abs(spread_val)}"

    ml_str = ""
    if context["home_ml"] and context["away_ml"]:
        ml_str = f"ML: {context['home_team']} {context['home_ml']:+d} / {context['away_team']} {context['away_ml']:+d}"

    # Build KenPom section if data is available
    kenpom_section = ""
    home_kp = context.get("home_kenpom")
    away_kp = context.get("away_kenpom")

    if home_kp or away_kp:
        kenpom_section = "\n## KENPOM ADVANCED ANALYTICS\n"

        if home_kp:
            kenpom_section += f"""
**{context['home_team']}** (KenPom #{home_kp.get('rank', 'N/A')})
- Adj. Efficiency Margin: {home_kp.get('adj_efficiency_margin', 'N/A')}
- Adj. Offense: {home_kp.get('adj_offense', 'N/A')} (#{home_kp.get('adj_offense_rank', 'N/A')})
- Adj. Defense: {home_kp.get('adj_defense', 'N/A')} (#{home_kp.get('adj_defense_rank', 'N/A')})
- Adj. Tempo: {home_kp.get('adj_tempo', 'N/A')} (#{home_kp.get('adj_tempo_rank', 'N/A')})
- Strength of Schedule: {home_kp.get('sos_adj_em', 'N/A')} (#{home_kp.get('sos_adj_em_rank', 'N/A')})
- Luck: {home_kp.get('luck', 'N/A')} (#{home_kp.get('luck_rank', 'N/A')})
- Record: {home_kp.get('wins', 0)}-{home_kp.get('losses', 0)}
"""

        if away_kp:
            kenpom_section += f"""
**{context['away_team']}** (KenPom #{away_kp.get('rank', 'N/A')})
- Adj. Efficiency Margin: {away_kp.get('adj_efficiency_margin', 'N/A')}
- Adj. Offense: {away_kp.get('adj_offense', 'N/A')} (#{away_kp.get('adj_offense_rank', 'N/A')})
- Adj. Defense: {away_kp.get('adj_defense', 'N/A')} (#{away_kp.get('adj_defense_rank', 'N/A')})
- Adj. Tempo: {away_kp.get('adj_tempo', 'N/A')} (#{away_kp.get('adj_tempo_rank', 'N/A')})
- Strength of Schedule: {away_kp.get('sos_adj_em', 'N/A')} (#{away_kp.get('sos_adj_em_rank', 'N/A')})
- Luck: {away_kp.get('luck', 'N/A')} (#{away_kp.get('luck_rank', 'N/A')})
- Record: {away_kp.get('wins', 0)}-{away_kp.get('losses', 0)}
"""

    # Build analysis considerations based on available data
    analysis_points = """1. Ranking differential and what it implies about team quality
2. Home court advantage (if applicable)
3. Conference game dynamics (teams know each other well)
4. Historical patterns for similar matchups (ranked vs unranked, etc.)
5. Line value - is the spread accurate?"""

    if home_kp or away_kp:
        analysis_points = """1. KenPom efficiency differentials (AdjO vs opponent AdjD matchups)
2. Tempo implications (fast vs slow matchup, how it affects total)
3. Strength of schedule context (are records inflated/deflated?)
4. Luck factor - teams with high luck may regress
5. Home court advantage (typically worth ~3.5 points)
6. Line value - does the spread align with KenPom predicted margin?"""

    prompt = f"""You are an expert college basketball betting analyst with deep knowledge of advanced analytics. Analyze this matchup and provide betting recommendations.

## MATCHUP
**{context['away_team']}** ({away_rank_str}) @ **{context['home_team']}** ({home_rank_str})
Date: {context['date']}
Venue: {context['venue'] or 'TBD'}
{'Neutral Site' if context['neutral_site'] else ''}

## BETTING LINES
Spread: {spread_str or 'Not available'}
{ml_str}
Total: O/U {context['total'] or 'N/A'}
{kenpom_section}
## CONTEXT
- Conference Game: {'Yes' if context['is_conference_game'] else 'No'}
- Same Conference: {'Yes' if context['home_conference'] == context['away_conference'] else 'No'}
- Tournament Game: {'Yes' if context['is_tournament'] else 'No'}

## YOUR ANALYSIS TASK

Provide a concise betting analysis. Consider:
{analysis_points}

## REQUIRED OUTPUT FORMAT

Respond in JSON format with exactly these fields:
{{
    "recommended_bet": "home_spread" | "away_spread" | "home_ml" | "away_ml" | "over" | "under" | "pass",
    "confidence_score": <float 0.0-1.0>,
    "key_factors": [<list of 3-5 key factors as strings>],
    "reasoning": "<2-3 sentence explanation of your recommendation>"
}}

Important guidelines:
- Only recommend bets with positive expected value
- If no clear edge exists, recommend "pass"
- confidence_score should reflect your certainty (0.5 = coin flip, 0.8+ = strong conviction)
- Be specific about WHY you see value, not just team quality
- When KenPom data is available, use efficiency margins to estimate expected point differential

Respond with ONLY the JSON object, no additional text."""

    return prompt


def analyze_with_claude(context: dict) -> dict:
    """Run analysis using Claude."""
    if not claude_client:
        raise ValueError("Claude API key not configured")

    prompt = build_analysis_prompt(context)
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]

    response = claude_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # Parse response
    response_text = response.content[0].text
    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    try:
        # Try to extract JSON from response
        analysis = json.loads(response_text)
    except json.JSONDecodeError:
        # If response isn't pure JSON, try to extract it
        import re
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            analysis = {
                "recommended_bet": "pass",
                "confidence_score": 0.5,
                "key_factors": ["Unable to parse AI response"],
                "reasoning": response_text[:500],
            }

    return {
        "ai_provider": "claude",
        "model_used": "claude-sonnet-4-20250514",
        "analysis_type": "matchup",
        "prompt_hash": prompt_hash,
        "response": response_text,
        "recommended_bet": analysis.get("recommended_bet", "pass"),
        "confidence_score": analysis.get("confidence_score", 0.5),
        "key_factors": analysis.get("key_factors", []),
        "reasoning": analysis.get("reasoning", ""),
        "tokens_used": tokens_used,
    }


def analyze_with_grok(context: dict) -> dict:
    """Run analysis using Grok."""
    if not grok_client:
        raise ValueError("Grok API key not configured")

    prompt = build_analysis_prompt(context)
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]

    response = grok_client.chat.completions.create(
        model="grok-2-latest",  # or grok-beta depending on access
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=1024,
    )

    response_text = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0

    try:
        analysis = json.loads(response_text)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            analysis = {
                "recommended_bet": "pass",
                "confidence_score": 0.5,
                "key_factors": ["Unable to parse AI response"],
                "reasoning": response_text[:500],
            }

    return {
        "ai_provider": "grok",
        "model_used": "grok-2-latest",
        "analysis_type": "matchup",
        "prompt_hash": prompt_hash,
        "response": response_text,
        "recommended_bet": analysis.get("recommended_bet", "pass"),
        "confidence_score": analysis.get("confidence_score", 0.5),
        "key_factors": analysis.get("key_factors", []),
        "reasoning": analysis.get("reasoning", ""),
        "tokens_used": tokens_used,
    }


def analyze_game(game_id: str, provider: AIProvider = "claude", save: bool = True) -> dict:
    """
    Run AI analysis on a game.

    Args:
        game_id: The game UUID
        provider: Which AI to use ("claude" or "grok")
        save: Whether to save the analysis to the database

    Returns:
        Analysis result dict
    """
    # Build context
    context = build_game_context(game_id)

    # Run analysis
    if provider == "claude":
        analysis = analyze_with_claude(context)
    elif provider == "grok":
        analysis = analyze_with_grok(context)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Add game_id to analysis
    analysis["game_id"] = game_id

    # Save to database
    if save:
        saved = insert_ai_analysis(analysis)
        analysis["id"] = saved["id"]
        analysis["created_at"] = saved["created_at"]

    return analysis


def get_quick_recommendation(context: dict) -> dict:
    """
    Get a quick betting recommendation without using the full AI.

    Uses simple heuristics based on rankings and spreads.
    """
    home_rank = context.get("home_rank")
    away_rank = context.get("away_rank")
    spread = context.get("spread")
    is_conf = context.get("is_conference_game", False)

    recommendation = "pass"
    confidence = 0.5
    reasoning = "No clear edge detected"

    # Conference contrarian logic
    if is_conf and spread is not None:
        # If one team is ranked and one is not
        if home_rank and not away_rank:
            # Home team ranked, away unranked
            if home_rank <= 5 and spread <= -12:
                # Top 5 team at big spread - underdog might cover
                recommendation = "away_spread"
                confidence = 0.58
                reasoning = f"Top 5 teams often don't cover large conference spreads. Historical data shows underdogs cover at ~57% when spread is 12+."
        elif away_rank and not home_rank:
            # Away team ranked, home unranked
            if away_rank <= 5 and spread >= 12:
                recommendation = "home_spread"
                confidence = 0.58
                reasoning = f"Unranked home teams against Top 5 road teams cover at elevated rates in conference play."

    return {
        "recommended_bet": recommendation,
        "confidence_score": confidence,
        "reasoning": reasoning,
        "source": "heuristic",
    }


class AIAnalyzer:
    """Main class for AI analysis - maintains state and caching."""

    def __init__(self):
        self.cache = {}

    def analyze(
        self,
        game_id: str,
        provider: AIProvider = "claude",
        use_cache: bool = True,
        save: bool = True
    ) -> dict:
        """Analyze a game with optional caching."""
        cache_key = f"{game_id}:{provider}"

        if use_cache and cache_key in self.cache:
            return self.cache[cache_key]

        result = analyze_game(game_id, provider, save)
        self.cache[cache_key] = result

        return result

    def analyze_both(self, game_id: str, save: bool = True) -> dict:
        """Run analysis with both Claude and Grok."""
        results = {}

        if claude_client:
            try:
                results["claude"] = analyze_game(game_id, "claude", save)
            except Exception as e:
                results["claude_error"] = str(e)

        if grok_client:
            try:
                results["grok"] = analyze_game(game_id, "grok", save)
            except Exception as e:
                results["grok_error"] = str(e)

        # Combine recommendations
        if "claude" in results and "grok" in results:
            claude_rec = results["claude"]["recommended_bet"]
            grok_rec = results["grok"]["recommended_bet"]

            if claude_rec == grok_rec and claude_rec != "pass":
                results["consensus"] = {
                    "recommended_bet": claude_rec,
                    "confidence_score": (
                        results["claude"]["confidence_score"] +
                        results["grok"]["confidence_score"]
                    ) / 2,
                    "reasoning": "Both AI models agree on this recommendation.",
                }
            else:
                results["consensus"] = {
                    "recommended_bet": "pass",
                    "confidence_score": 0.5,
                    "reasoning": "AI models disagree - no consensus recommendation.",
                }

        return results

    def clear_cache(self):
        """Clear the analysis cache."""
        self.cache = {}


# Global analyzer instance
analyzer = AIAnalyzer()
