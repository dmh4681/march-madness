"""
AI Service for game analysis using Claude and Grok.

Provides betting analysis and recommendations using LLMs.

SECURITY NOTES:
- API keys are loaded from environment variables, never hardcoded
- Error messages are sanitized to prevent key leakage
- API key values are never logged
"""

import os
import re
import json
import hashlib
import logging
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
    get_team_haslametrics,
    get_game_prediction_markets,
    get_game_arbitrage_opportunities,
    insert_ai_analysis,
)

load_dotenv()

logger = logging.getLogger(__name__)

# API Keys - loaded from environment, never hardcoded
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = "https://api.x.ai/v1"  # Grok uses OpenAI-compatible API

# Initialize clients
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
grok_client = OpenAI(api_key=GROK_API_KEY, base_url=GROK_BASE_URL) if GROK_API_KEY else None

AIProvider = Literal["claude", "grok"]


# =============================================================================
# SECURITY: Error Message Sanitization
# =============================================================================

# Patterns that might contain sensitive information
_SENSITIVE_PATTERNS = [
    # API key patterns
    r'sk-ant-api[a-zA-Z0-9_-]+',  # Anthropic
    r'xai-[a-zA-Z0-9_-]+',  # Grok/xAI
    r'sk-[a-zA-Z0-9_-]{40,}',  # OpenAI-style
    r'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',  # JWT tokens
    # Email/password patterns
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # Emails
    r'password[=:]\s*[^\s,]+',  # Password values
    # Connection strings
    r'postgresql://[^\s]+',
    r'https://[a-zA-Z0-9-]+\.supabase\.co/[^\s]+',
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _SENSITIVE_PATTERNS]


def _sanitize_error_message(error_msg: str) -> str:
    """
    Sanitize an error message to remove any potentially sensitive information.

    SECURITY: This function ensures that API keys, tokens, passwords, and other
    sensitive data are not exposed in error messages returned to clients or logged.

    Args:
        error_msg: The original error message

    Returns:
        Sanitized error message with sensitive patterns replaced
    """
    if not error_msg:
        return "An error occurred"

    sanitized = error_msg

    # Replace known sensitive patterns
    for pattern in _COMPILED_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)

    # Also check for common API key environment variable names in error messages
    # and redact values that follow them
    env_var_pattern = re.compile(
        r'(ANTHROPIC_API_KEY|GROK_API_KEY|SUPABASE_SERVICE_KEY|ODDS_API_KEY|'
        r'KENPOM_PASSWORD|REFRESH_API_KEY|KALSHI_API_KEY)[=:\s]+[^\s,]+',
        re.IGNORECASE
    )
    sanitized = env_var_pattern.sub(r'\1=[REDACTED]', sanitized)

    # Truncate very long error messages that might contain dumps
    max_length = 500
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... [truncated]"

    return sanitized


def _extract_json_from_response(response_text: str) -> dict:
    """
    Extract JSON from AI response text, handling nested braces.

    Tries multiple strategies:
    1. Direct JSON parse
    2. Find JSON block markers (```json ... ```)
    3. Find outermost { } with brace counting
    4. Fallback to default values

    Args:
        response_text: Raw text response from AI

    Returns:
        Parsed JSON dict or default fallback values
    """
    # Strategy 1: Try direct parse
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Look for ```json code blocks
    json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find outermost JSON object using brace counting
    # This handles nested braces like {"key_factors": ["a", "b"]}
    start_idx = response_text.find('{')
    if start_idx != -1:
        brace_count = 0
        end_idx = start_idx

        for i, char in enumerate(response_text[start_idx:], start=start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break

        if brace_count == 0:
            json_str = response_text[start_idx:end_idx + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

    # Strategy 4: Fallback
    return {
        "recommended_bet": "pass",
        "confidence_score": 0.5,
        "key_factors": ["Unable to parse AI response"],
        "reasoning": response_text[:500] if response_text else "No response",
    }


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

    # Get Haslametrics ratings
    home_haslametrics = None
    away_haslametrics = None
    if game.get("home_team_id"):
        home_haslametrics = get_team_haslametrics(game["home_team_id"], game["season"])
    if game.get("away_team_id"):
        away_haslametrics = get_team_haslametrics(game["away_team_id"], game["season"])

    # Get prediction market data
    prediction_markets = get_game_prediction_markets(game_id)
    arbitrage_opportunities = get_game_arbitrage_opportunities(game_id)

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
        # Haslametrics data
        "home_haslametrics": home_haslametrics,
        "away_haslametrics": away_haslametrics,
        # Prediction market data
        "prediction_markets": prediction_markets,
        "arbitrage_opportunities": arbitrage_opportunities,
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

    # Build Haslametrics section if data is available
    haslametrics_section = ""
    home_hasla = context.get("home_haslametrics")
    away_hasla = context.get("away_haslametrics")

    if home_hasla or away_hasla:
        haslametrics_section = "\n## HASLAMETRICS ANALYTICS (All-Play Methodology)\n"

        if home_hasla:
            haslametrics_section += f"""
**{context['home_team']}** (Haslametrics #{home_hasla.get('rank', 'N/A')})
- Offensive Efficiency: {home_hasla.get('offensive_efficiency', 'N/A')}
- Defensive Efficiency: {home_hasla.get('defensive_efficiency', 'N/A')}
- All-Play %: {home_hasla.get('all_play_pct', 'N/A')} (probability of beating average D1 team)
- Momentum: {home_hasla.get('momentum_overall', 'N/A')} (O: {home_hasla.get('momentum_offense', 'N/A')}, D: {home_hasla.get('momentum_defense', 'N/A')})
- Pace: {home_hasla.get('pace', 'N/A')}
- SOS: {home_hasla.get('sos', 'N/A')} (#{home_hasla.get('sos_rank', 'N/A')})
- Last 5: {home_hasla.get('last_5_record', 'N/A')}
- Quadrant Records: Q1: {home_hasla.get('quad_1_record', 'N/A')}, Q2: {home_hasla.get('quad_2_record', 'N/A')}
"""

        if away_hasla:
            haslametrics_section += f"""
**{context['away_team']}** (Haslametrics #{away_hasla.get('rank', 'N/A')})
- Offensive Efficiency: {away_hasla.get('offensive_efficiency', 'N/A')}
- Defensive Efficiency: {away_hasla.get('defensive_efficiency', 'N/A')}
- All-Play %: {away_hasla.get('all_play_pct', 'N/A')} (probability of beating average D1 team)
- Momentum: {away_hasla.get('momentum_overall', 'N/A')} (O: {away_hasla.get('momentum_offense', 'N/A')}, D: {away_hasla.get('momentum_defense', 'N/A')})
- Pace: {away_hasla.get('pace', 'N/A')}
- SOS: {away_hasla.get('sos', 'N/A')} (#{away_hasla.get('sos_rank', 'N/A')})
- Last 5: {away_hasla.get('last_5_record', 'N/A')}
- Quadrant Records: Q1: {away_hasla.get('quad_1_record', 'N/A')}, Q2: {away_hasla.get('quad_2_record', 'N/A')}
"""

    # Build prediction market section if data is available
    pm_section = ""
    prediction_markets = context.get("prediction_markets", [])
    arbitrage = context.get("arbitrage_opportunities", [])

    if prediction_markets or arbitrage:
        pm_section = "\n## PREDICTION MARKET DATA\n"

        if prediction_markets:
            for pm in prediction_markets[:3]:  # Limit to 3 markets
                pm_section += f"\n**{pm.get('source', 'Unknown').title()}**: {pm.get('title', 'N/A')}\n"
                for outcome in pm.get("outcomes", [])[:4]:
                    price = outcome.get("price", 0) or 0
                    pm_section += f"  - {outcome.get('name', 'N/A')}: {price*100:.1f}%\n"
                if pm.get("volume"):
                    pm_section += f"  - Volume: ${pm.get('volume', 0):,.0f}\n"

        if arbitrage:
            pm_section += "\n**Arbitrage Signals:**\n"
            for arb in arbitrage[:3]:  # Limit to 3 opportunities
                direction = "higher" if arb.get("edge_direction") == "prediction_higher" else "lower"
                sbook_prob = arb.get('sportsbook_implied_prob', 0) or 0
                pm_prob = arb.get('prediction_market_prob', 0) or 0
                delta = arb.get('delta', 0) or 0
                pm_section += f"""
- {arb.get('bet_type', 'N/A').replace('_', ' ').title()}:
  - Sportsbook implied: {sbook_prob*100:.1f}%
  - Prediction market: {pm_prob*100:.1f}%
  - Delta: {delta:.1f}% ({direction} on prediction market)
  - Actionable: {"YES" if arb.get('is_actionable') else "No"}
"""

    # Build analysis considerations based on available data
    analysis_points = """1. Ranking differential and what it implies about team quality
2. Home court advantage (if applicable)
3. Conference game dynamics (teams know each other well)
4. Historical patterns for similar matchups (ranked vs unranked, etc.)
5. Line value - is the spread accurate?"""

    has_kenpom = home_kp or away_kp
    has_haslametrics = home_hasla or away_hasla

    if has_kenpom and has_haslametrics:
        # Both analytics sources available - comprehensive analysis
        analysis_points = """1. Cross-validate KenPom AdjEM vs Haslametrics efficiency (look for agreement/disagreement)
2. Momentum indicators from Haslametrics - is one team trending up/down?
3. All-Play % comparison as baseline win probability estimate
4. Tempo matchup implications (KenPom tempo vs Haslametrics pace)
5. Quadrant record context for quality of wins
6. Luck factor (KenPom) - teams with high luck may regress
7. Recent form (Last 5) vs season-long metrics
8. Line value - does spread align with both models' expectations?"""
    elif has_kenpom:
        analysis_points = """1. KenPom efficiency differentials (AdjO vs opponent AdjD matchups)
2. Tempo implications (fast vs slow matchup, how it affects total)
3. Strength of schedule context (are records inflated/deflated?)
4. Luck factor - teams with high luck may regress
5. Home court advantage (typically worth ~3.5 points)
6. Line value - does the spread align with KenPom predicted margin?"""
    elif has_haslametrics:
        analysis_points = """1. Haslametrics efficiency comparison and All-Play % difference
2. Momentum indicators - which team is trending in the right direction?
3. Recent form (Last 5) as indicator of current team quality
4. Quadrant records context for quality of wins/losses
5. Home court advantage (if applicable)
6. Line value - does the spread align with Haslametrics rankings?"""

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
{kenpom_section}{haslametrics_section}{pm_section}
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
- When Haslametrics data is available, use All-Play % and momentum to validate your pick
- If KenPom and Haslametrics disagree significantly, lower your confidence score
- When prediction market data is available, consider where public money is flowing
- Large deltas between prediction markets and sportsbooks may signal market inefficiency
- Actionable arbitrage signals (>=10% delta) warrant serious consideration

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

    # Extract JSON using robust parser that handles nested braces
    analysis = _extract_json_from_response(response_text)

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
        model="grok-3",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=1024,
    )

    response_text = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0

    # Extract JSON using robust parser that handles nested braces
    analysis = _extract_json_from_response(response_text)

    return {
        "ai_provider": "grok",
        "model_used": "grok-3",
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
                # SECURITY: Sanitize error message to avoid leaking API key info
                results["claude_error"] = _sanitize_error_message(str(e))

        if grok_client:
            try:
                results["grok"] = analyze_game(game_id, "grok", save)
            except Exception as e:
                # SECURITY: Sanitize error message to avoid leaking API key info
                results["grok_error"] = _sanitize_error_message(str(e))

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
