"""
AI Service for Game Analysis using Claude and Grok

Provides AI-powered betting analysis and recommendations using Large Language Models.

Architecture Overview:
=====================
This module orchestrates AI analysis by:
1. Building comprehensive game context from multiple data sources
2. Constructing optimized prompts with all available analytics
3. Calling Claude (Anthropic) or Grok (xAI) APIs
4. Parsing structured JSON responses
5. Storing analyses in database for caching/historical reference

Data Sources Used in AI Prompts:
================================
1. Basic Game Info: Teams, date, venue, neutral site flag
2. Rankings: AP poll rankings for both teams
3. Betting Lines: Spread, moneylines, total (from The Odds API)
4. KenPom Analytics: AdjO, AdjD, AdjEM, tempo, SOS, luck
5. Haslametrics: All-Play %, momentum, efficiency, quadrant records
6. Prediction Markets: Polymarket/Kalshi prices and arbitrage signals

AI Prompt Strategy:
==================
The prompt is structured to leverage AI strengths:
- Provides raw data, asks for interpretation
- Requests specific JSON output format for reliable parsing
- Adjusts analysis instructions based on available data
- When both KenPom and Haslametrics available, asks for cross-validation
- Includes prediction market data when significant edges detected

AI Response Parsing:
===================
AI responses are parsed with _extract_json_from_response() which tries:
1. Direct JSON parse (if AI follows format exactly)
2. JSON code block extraction (```json...```)
3. Brace-counting JSON extraction (handles nested objects)
4. Fallback to default "pass" recommendation

SECURITY NOTES:
- API keys are loaded from environment variables, never hardcoded
- Error messages are sanitized to prevent key leakage via _sanitize_error_message()
- API key values are never logged
- Sensitive patterns (API keys, JWTs, emails) are detected and redacted
"""

import os
import re
import json
import hashlib
import logging
import time
import random
from datetime import datetime, timezone
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
    get_ai_analysis_by_provider,
    get_tournament,
    get_tournament_game_data,
    upsert_bracket_pick,
)

try:
    from backend.utils.retry import (
        _jitter_delay,
        RateLimitError,
        claude_breaker,
        grok_breaker,
        CircuitBreakerOpen,
    )
except ImportError:
    from ..utils.retry import (
        _jitter_delay,
        RateLimitError,
        claude_breaker,
        grok_breaker,
        CircuitBreakerOpen,
    )

try:
    from backend.utils.cache import TTLCache
except ImportError:
    from ..utils.cache import TTLCache

load_dotenv()

# =============================================================================
# AI Analysis Cache
# =============================================================================
# L1 in-memory cache for AI analysis results.
# TTL: 6 hours — long enough to avoid redundant AI calls within a session,
# short enough that stale spreads/line moves don't persist too long.
# The database (ai_analysis table) serves as the L2 persistent cache.
ANALYSIS_CACHE_TTL_SECONDS = 6 * 3600  # 6 hours

ai_analysis_cache = TTLCache(default_ttl=ANALYSIS_CACHE_TTL_SECONDS)

logger = logging.getLogger(__name__)

# API Keys - loaded from environment, never hardcoded
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = "https://api.x.ai/v1"  # Grok uses OpenAI-compatible API

# Initialize clients with timeouts (seconds)
AI_TIMEOUT = 60  # 60s timeout for AI API calls
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=AI_TIMEOUT) if ANTHROPIC_API_KEY else None
grok_client = OpenAI(api_key=GROK_API_KEY, base_url=GROK_BASE_URL, timeout=AI_TIMEOUT) if GROK_API_KEY else None

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


def _sanitize_prompt_value(value: str, max_length: int = 100) -> str:
    """
    Sanitize a value before interpolating it into an AI prompt.

    Strips characters that could be used for prompt injection (markdown
    headers, system-role markers, etc.) and enforces a length limit.
    """
    if not value:
        return "Unknown"
    sanitized = value[:max_length]
    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')
    # Strip markdown/prompt-injection patterns: #, ```, ---, >>
    sanitized = re.sub(r'[#`>]', '', sanitized)
    # Collapse whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized or "Unknown"


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
    """
    Build comprehensive context object for AI analysis.

    This function aggregates data from ALL available sources to provide
    the AI with maximum information for analysis. The more data available,
    the better the analysis quality.

    Data Aggregation Flow:
    =====================
    1. Fetch game record (teams, date, venue, conference info)
    2. Fetch latest spread from spreads table
    3. Fetch AP rankings for both teams
    4. Fetch KenPom ratings (if available - requires subscription)
    5. Fetch Haslametrics ratings (always available - FREE)
    6. Fetch prediction market data (if games are matched)
    7. Fetch arbitrage opportunities (if detected)

    The resulting context dict contains all this data in a flat structure
    that's easy to template into the AI prompt.

    Args:
        game_id: UUID of the game to analyze

    Returns:
        Dict with all available game context

    Raises:
        ValueError: If game_id doesn't exist in database
    """
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
    """
    Build the analysis prompt for the AI.

    Prompt Engineering Strategy:
    ===========================
    The prompt is carefully structured to elicit useful betting analysis:

    1. Role Setting: "Expert college basketball betting analyst"
       - Establishes domain expertise expectation
       - Primes AI for betting-specific vocabulary

    2. Data Presentation: Structured sections with clear labels
       - MATCHUP: Teams, rankings, date, venue
       - BETTING LINES: Spread, moneylines, total
       - KENPOM ANALYTICS: Efficiency, tempo, luck (when available)
       - HASLAMETRICS: All-Play %, momentum (when available)
       - PREDICTION MARKETS: Market prices, arbitrage signals

    3. Analysis Instructions: Vary based on available data
       - Basic: Rankings, home court, line value
       - With KenPom: Efficiency matchups, tempo implications
       - With Haslametrics: Momentum, quadrant context
       - With Both: Cross-validation, divergence detection

    4. Output Format: Strict JSON structure
       - recommended_bet: Specific bet type
       - confidence_score: 0.0-1.0 scale
       - key_factors: List of driving factors
       - reasoning: Explanation for recommendation

    5. Value Focus: "Only recommend bets with positive expected value"
       - Encourages conservative recommendations
       - "pass" option for unclear situations

    Returns:
        Complete prompt string ready for AI API call
    """
    home_rank_str = f"#{context['home_rank']}" if context["home_rank"] else "Unranked"
    away_rank_str = f"#{context['away_rank']}" if context["away_rank"] else "Unranked"

    # Sanitize team names before prompt interpolation to prevent injection
    home_team = _sanitize_prompt_value(context.get("home_team", "Unknown"))
    away_team = _sanitize_prompt_value(context.get("away_team", "Unknown"))

    spread_str = ""
    if context["spread"] is not None:
        spread_val = context["spread"]
        if spread_val < 0:
            spread_str = f"{home_team} -{abs(spread_val)}"
        else:
            spread_str = f"{away_team} -{abs(spread_val)}"

    ml_str = ""
    if context["home_ml"] and context["away_ml"]:
        ml_str = f"ML: {home_team} {context['home_ml']:+d} / {away_team} {context['away_ml']:+d}"

    # ==========================================================================
    # KenPom Section: Advanced efficiency-based analytics
    # These metrics help the AI understand true team quality vs record
    #
    # Key metrics explained in prompt context:
    # - AdjEM: Adjusted Efficiency Margin = AdjO - AdjD (main power rating)
    # - AdjO: Points scored per 100 possessions (higher = better offense)
    # - AdjD: Points allowed per 100 possessions (LOWER = better defense)
    # - Tempo: Possessions per game (fast = more variance, more scoring)
    # - Luck: Deviation from expected record (high luck = regression candidate)
    # - SOS: Strength of schedule (contextualizes win-loss record)
    # ==========================================================================
    kenpom_section = ""
    home_kp = context.get("home_kenpom")
    away_kp = context.get("away_kenpom")

    if home_kp or away_kp:
        kenpom_section = "\n## KENPOM ADVANCED ANALYTICS\n"

        if home_kp:
            kenpom_section += f"""
**{home_team}** (KenPom #{home_kp.get('rank', 'N/A')})
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
**{away_team}** (KenPom #{away_kp.get('rank', 'N/A')})
- Adj. Efficiency Margin: {away_kp.get('adj_efficiency_margin', 'N/A')}
- Adj. Offense: {away_kp.get('adj_offense', 'N/A')} (#{away_kp.get('adj_offense_rank', 'N/A')})
- Adj. Defense: {away_kp.get('adj_defense', 'N/A')} (#{away_kp.get('adj_defense_rank', 'N/A')})
- Adj. Tempo: {away_kp.get('adj_tempo', 'N/A')} (#{away_kp.get('adj_tempo_rank', 'N/A')})
- Strength of Schedule: {away_kp.get('sos_adj_em', 'N/A')} (#{away_kp.get('sos_adj_em_rank', 'N/A')})
- Luck: {away_kp.get('luck', 'N/A')} (#{away_kp.get('luck_rank', 'N/A')})
- Record: {away_kp.get('wins', 0)}-{away_kp.get('losses', 0)}
"""

    # ==========================================================================
    # Haslametrics Section: All-Play methodology and momentum metrics
    # Provides complementary view to KenPom with different strengths:
    #
    # Key metrics explained in prompt context:
    # - All-Play %: Win probability vs average D1 team (intuitive power rating)
    # - Momentum (overall/O/D): Recent trend direction (-1 to +1 scale)
    #   Positive momentum = team improving, valuable for finding value
    # - Quadrant Records: Performance vs NET quadrants (Q1 = best opponents)
    #   Strong Q1 records indicate true tournament quality
    # - Last 5: Recent form indicator, useful for detecting streaks/slumps
    #
    # When both KenPom and Haslametrics available, AI is instructed to
    # cross-validate: disagreement lowers confidence, agreement increases it
    # ==========================================================================
    haslametrics_section = ""
    home_hasla = context.get("home_haslametrics")
    away_hasla = context.get("away_haslametrics")

    if home_hasla or away_hasla:
        haslametrics_section = "\n## HASLAMETRICS ANALYTICS (All-Play Methodology)\n"

        if home_hasla:
            haslametrics_section += f"""
**{home_team}** (Haslametrics #{home_hasla.get('rank', 'N/A')})
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
**{away_team}** (Haslametrics #{away_hasla.get('rank', 'N/A')})
- Offensive Efficiency: {away_hasla.get('offensive_efficiency', 'N/A')}
- Defensive Efficiency: {away_hasla.get('defensive_efficiency', 'N/A')}
- All-Play %: {away_hasla.get('all_play_pct', 'N/A')} (probability of beating average D1 team)
- Momentum: {away_hasla.get('momentum_overall', 'N/A')} (O: {away_hasla.get('momentum_offense', 'N/A')}, D: {away_hasla.get('momentum_defense', 'N/A')})
- Pace: {away_hasla.get('pace', 'N/A')}
- SOS: {away_hasla.get('sos', 'N/A')} (#{away_hasla.get('sos_rank', 'N/A')})
- Last 5: {away_hasla.get('last_5_record', 'N/A')}
- Quadrant Records: Q1: {away_hasla.get('quad_1_record', 'N/A')}, Q2: {away_hasla.get('quad_2_record', 'N/A')}
"""

    # ==========================================================================
    # Prediction Market Section: Polymarket and Kalshi data
    # Provides "wisdom of crowds" signal complementary to sportsbooks
    #
    # Key concepts:
    # - Prediction markets price events as probabilities (0-100%)
    # - Sportsbooks use odds (-110, +150) which imply probabilities
    # - When these diverge significantly, arbitrage may exist
    #
    # Arbitrage Detection:
    # - Delta = difference between sportsbook implied prob and PM prob
    # - Actionable threshold: >=10% delta
    # - Large deltas suggest one market is mispriced
    #
    # Example: If sportsbook implies Duke 60% to cover but Polymarket
    # prices Duke cover at 50%, there may be value on the other side
    # ==========================================================================
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

    # ==========================================================================
    # Dynamic Analysis Instructions
    # The AI is given different analytical frameworks based on what data
    # is available. This ensures the AI focuses on relevant factors and
    # doesn't hallucinate about missing data.
    #
    # Hierarchy of analysis depth:
    # 1. Both KenPom + Haslametrics: Full cross-validation, highest quality
    # 2. KenPom only: Efficiency-focused analysis
    # 3. Haslametrics only: Momentum and All-Play % focused
    # 4. Neither: Basic ranking/spread analysis (lowest quality)
    # ==========================================================================
    analysis_points = """1. Ranking differential and what it implies about team quality
2. Home court advantage (if applicable)
3. Conference game dynamics (teams know each other well)
4. Historical patterns for similar matchups (ranked vs unranked, etc.)
5. Line value - is the spread accurate?"""

    has_kenpom = home_kp or away_kp
    has_haslametrics = home_hasla or away_hasla

    if has_kenpom and has_haslametrics:
        # BEST CASE: Both analytics sources available
        # AI can cross-validate between sources for highest confidence
        # Disagreement between sources should lower confidence
        analysis_points = """1. Cross-validate KenPom AdjEM vs Haslametrics efficiency (look for agreement/disagreement)
2. Momentum indicators from Haslametrics - is one team trending up/down?
3. All-Play % comparison as baseline win probability estimate
4. Tempo matchup implications (KenPom tempo vs Haslametrics pace)
5. Quadrant record context for quality of wins
6. Luck factor (KenPom) - teams with high luck may regress
7. Recent form (Last 5) vs season-long metrics
8. Line value - does spread align with both models' expectations?"""
    elif has_kenpom:
        # KenPom only: Focus on efficiency-based analysis
        # Can estimate point differential from AdjEM difference
        analysis_points = """1. KenPom efficiency differentials (AdjO vs opponent AdjD matchups)
2. Tempo implications (fast vs slow matchup, how it affects total)
3. Strength of schedule context (are records inflated/deflated?)
4. Luck factor - teams with high luck may regress
5. Home court advantage (typically worth ~3.5 points)
6. Line value - does the spread align with KenPom predicted margin?"""
    elif has_haslametrics:
        # Haslametrics only: Focus on All-Play % and momentum
        # Good for identifying trending teams
        analysis_points = """1. Haslametrics efficiency comparison and All-Play % difference
2. Momentum indicators - which team is trending in the right direction?
3. Recent form (Last 5) as indicator of current team quality
4. Quadrant records context for quality of wins/losses
5. Home court advantage (if applicable)
6. Line value - does the spread align with Haslametrics rankings?"""

    prompt = f"""You are an expert college basketball betting analyst with deep knowledge of advanced analytics. Analyze this matchup and provide betting recommendations.

## MATCHUP
**{away_team}** ({away_rank_str}) @ **{home_team}** ({home_rank_str})
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


def build_tournament_pick_prompt(context: dict, matchup_metadata: dict) -> str:
    """
    Build a tournament-specific prompt for bracket pick generation.

    Unlike build_analysis_prompt() which recommends a BET TYPE (spread, ML, etc.),
    this prompt asks the AI to pick a WINNER for single-elimination tournament play.

    Args:
        context: Game context dict from build_game_context()
        matchup_metadata: Dict with tournament-specific data:
            - home_seed, away_seed
            - home_region, away_region
            - tournament_round
            - seed_history (historical win rate string)

    Returns:
        Complete prompt string for tournament pick generation
    """
    # Extract seed numbers and round for display in the prompt header.
    # Seeds provide the AI with base-rate priors (e.g. 1-seeds win 99.4%).
    home_seed = matchup_metadata.get("home_seed", "?")
    away_seed = matchup_metadata.get("away_seed", "?")
    tournament_round = matchup_metadata.get("tournament_round", "unknown")
    # Seed history is a pre-formatted string from SEED_MATCHUP_HISTORY constants
    # giving the AI historical win rates for this seed pairing (e.g. "1v16: 99.4%").
    seed_history = matchup_metadata.get("seed_history", "")

    # Convert round identifiers (e.g. "sweet_16") to display format ("Sweet 16")
    round_display = tournament_round.replace("_", " ").title()
    # Use either team's region — for non-Final Four games both should match
    region = matchup_metadata.get("home_region") or matchup_metadata.get("away_region") or "N/A"

    # Sanitize team names before prompt interpolation to prevent injection.
    # Strips markdown headers (#), backticks, and angle brackets (>) that could
    # alter prompt structure if a team name contained adversarial content.
    home_team = _sanitize_prompt_value(context.get("home_team", "Unknown"))
    away_team = _sanitize_prompt_value(context.get("away_team", "Unknown"))

    # Spread context (for reference, not the primary decision factor)
    spread_str = ""
    if context.get("spread") is not None:
        spread_val = context["spread"]
        if spread_val < 0:
            spread_str = f"{home_team} -{abs(spread_val)}"
        else:
            spread_str = f"{away_team} -{abs(spread_val)}"

    # KenPom section (same format as build_analysis_prompt)
    kenpom_section = ""
    home_kp = context.get("home_kenpom")
    away_kp = context.get("away_kenpom")

    if home_kp or away_kp:
        kenpom_section = "\n## KENPOM ADVANCED ANALYTICS\n"

        if home_kp:
            kenpom_section += f"""
**{home_team}** (KenPom #{home_kp.get('rank', 'N/A')})
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
**{away_team}** (KenPom #{away_kp.get('rank', 'N/A')})
- Adj. Efficiency Margin: {away_kp.get('adj_efficiency_margin', 'N/A')}
- Adj. Offense: {away_kp.get('adj_offense', 'N/A')} (#{away_kp.get('adj_offense_rank', 'N/A')})
- Adj. Defense: {away_kp.get('adj_defense', 'N/A')} (#{away_kp.get('adj_defense_rank', 'N/A')})
- Adj. Tempo: {away_kp.get('adj_tempo', 'N/A')} (#{away_kp.get('adj_tempo_rank', 'N/A')})
- Strength of Schedule: {away_kp.get('sos_adj_em', 'N/A')} (#{away_kp.get('sos_adj_em_rank', 'N/A')})
- Luck: {away_kp.get('luck', 'N/A')} (#{away_kp.get('luck_rank', 'N/A')})
- Record: {away_kp.get('wins', 0)}-{away_kp.get('losses', 0)}
"""

    # Haslametrics section (same format as build_analysis_prompt)
    haslametrics_section = ""
    home_hasla = context.get("home_haslametrics")
    away_hasla = context.get("away_haslametrics")

    if home_hasla or away_hasla:
        haslametrics_section = "\n## HASLAMETRICS ANALYTICS (All-Play Methodology)\n"

        if home_hasla:
            haslametrics_section += f"""
**{home_team}** (Haslametrics #{home_hasla.get('rank', 'N/A')})
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
**{away_team}** (Haslametrics #{away_hasla.get('rank', 'N/A')})
- Offensive Efficiency: {away_hasla.get('offensive_efficiency', 'N/A')}
- Defensive Efficiency: {away_hasla.get('defensive_efficiency', 'N/A')}
- All-Play %: {away_hasla.get('all_play_pct', 'N/A')} (probability of beating average D1 team)
- Momentum: {away_hasla.get('momentum_overall', 'N/A')} (O: {away_hasla.get('momentum_offense', 'N/A')}, D: {away_hasla.get('momentum_defense', 'N/A')})
- Pace: {away_hasla.get('pace', 'N/A')}
- SOS: {away_hasla.get('sos', 'N/A')} (#{away_hasla.get('sos_rank', 'N/A')})
- Last 5: {away_hasla.get('last_5_record', 'N/A')}
- Quadrant Records: Q1: {away_hasla.get('quad_1_record', 'N/A')}, Q2: {away_hasla.get('quad_2_record', 'N/A')}
"""

    # Dynamic analysis instructions based on available data.
    # The AI receives different analytical frameworks depending on what data sources
    # are available. This prevents hallucination about missing data and focuses the
    # AI on the most relevant factors for each scenario.
    #
    # Hierarchy (best to worst):
    #   1. Both KenPom + Haslametrics → cross-validation, highest confidence
    #   2. KenPom only → efficiency-focused, can estimate point differential
    #   3. Haslametrics only → momentum + All-Play % focused
    #   4. Neither → basic seed/spread/coaching analysis
    has_kenpom = home_kp or away_kp
    has_haslametrics = home_hasla or away_hasla

    if has_kenpom and has_haslametrics:
        # Best case: two independent data sources let the AI cross-validate.
        # When they agree, confidence rises; when they disagree, it should drop.
        analysis_points = """1. Cross-validate KenPom AdjEM vs Haslametrics efficiency to gauge true team quality
2. Momentum indicators — which team is trending up/down entering the tournament?
3. All-Play % comparison as baseline win probability
4. Tempo matchup — can the underdog control pace to keep it close?
5. Quadrant records for quality-of-wins context (Q1 wins = tournament-caliber opponents)
6. Luck factor (KenPom) — high-luck teams may regress in single-elimination
7. Recent form (Last 5) vs season-long metrics
8. Seed matchup historical precedent as base rate"""
    elif has_kenpom:
        analysis_points = """1. KenPom efficiency differentials (AdjO vs opponent AdjD matchups)
2. Tempo implications — can the underdog dictate pace?
3. Luck factor — high-luck teams often regress in March
4. Strength of schedule context (inflated vs battle-tested records)
5. Seed matchup historical precedent as base rate
6. Estimated point differential from AdjEM difference"""
    elif has_haslametrics:
        analysis_points = """1. Haslametrics efficiency comparison and All-Play % gap
2. Momentum indicators — which team is peaking at the right time?
3. Recent form (Last 5) for current team quality
4. Quadrant records — proven ability to beat good teams
5. Seed matchup historical precedent as base rate"""
    else:
        analysis_points = """1. Seed matchup historical precedent as base rate
2. Conference strength and quality of competition
3. Spread as market-implied probability (if available)
4. Tournament experience and coaching pedigree
5. Style matchup and upset potential"""

    prompt = f"""You are an expert NCAA Tournament bracket analyst. Your job is to pick the WINNER of this single-elimination tournament game. This is NOT a betting recommendation — you are predicting which team advances.

## MATCHUP — {round_display}
**#{away_seed} {away_team}** vs **#{home_seed} {home_team}**
Region: {region}
Date: {context['date']}
Venue: {context['venue'] or 'TBD'} (Neutral Site — no home court advantage)

## SEED MATCHUP HISTORY
{seed_history}

## BETTING LINES (market context)
Spread: {spread_str or 'Not available'}
Total: O/U {context.get('total') or 'N/A'}
{kenpom_section}{haslametrics_section}
## TOURNAMENT-SPECIFIC ANALYSIS

Consider these factors:
{analysis_points}

Additional tournament-specific factors:
- Single elimination magnifies variance — depth and bench scoring matter more
- Three-point shooting variance causes upsets (hot/cold shooting nights)
- Free throw shooting is critical in close tournament games
- Neutral site removes home court — focus on true talent gap
- Coaching experience in the tournament (preparation, adjustments)

## REQUIRED OUTPUT FORMAT

Respond in JSON format with exactly these fields:
{{
    "picked_team": "home" | "away",
    "confidence_score": <float 0.0-1.0>,
    "key_factors": [<list of 3-5 key factors as strings>],
    "reasoning": "<2-3 sentence explanation of why this team wins>"
}}

Important guidelines:
- "picked_team" MUST be exactly "home" or "away" (home = {home_team}, away = {away_team})
- confidence_score: 0.5 = pure coin flip, 0.7 = moderate, 0.85+ = very high
- For 1v16 and 2v15: very high confidence for the favorite is appropriate (historical ~99%)
- For 5v12, 6v11, 7v10: carefully evaluate upset potential (~30-40% upset rate historically)
- For 8v9: nearly a coin flip — analyze deeply before picking
- When KenPom and Haslametrics disagree, lower your confidence
- Factor in variance: single elimination rewards consistency and defense

Respond with ONLY the JSON object, no additional text."""

    return prompt


def build_combined_tournament_prompt(context: dict, matchup_metadata: dict) -> str:
    """
    Build a combined tournament prompt requesting both a bracket pick AND betting recommendation.

    This extends build_tournament_pick_prompt() by also asking the AI to evaluate
    the betting lines for the game. A single AI call returns a JSON object with
    both the tournament winner pick and a spread/moneyline betting recommendation.

    Args:
        context: Game context dict from build_game_context()
        matchup_metadata: Tournament metadata (home_seed, away_seed, home_region,
            away_region, tournament_round, seed_history)

    Returns:
        Combined prompt string for tournament analysis
    """
    home_seed = matchup_metadata.get("home_seed", "?")
    away_seed = matchup_metadata.get("away_seed", "?")
    tournament_round = matchup_metadata.get("tournament_round", "unknown")
    seed_history = matchup_metadata.get("seed_history", "")
    round_display = tournament_round.replace("_", " ").title()
    region = matchup_metadata.get("home_region") or matchup_metadata.get("away_region") or "N/A"

    home_team = _sanitize_prompt_value(context.get("home_team", "Unknown"))
    away_team = _sanitize_prompt_value(context.get("away_team", "Unknown"))

    # Spread context
    spread_str = ""
    if context.get("spread") is not None:
        spread_val = context["spread"]
        if spread_val < 0:
            spread_str = f"{home_team} -{abs(spread_val)}"
        else:
            spread_str = f"{away_team} -{abs(spread_val)}"

    # KenPom section
    kenpom_section = ""
    home_kp = context.get("home_kenpom")
    away_kp = context.get("away_kenpom")
    if home_kp or away_kp:
        kenpom_section = "\n## KENPOM ADVANCED ANALYTICS\n"
        if home_kp:
            kenpom_section += f"""
**{home_team}** (KenPom #{home_kp.get('rank', 'N/A')})
- Adj. Efficiency Margin: {home_kp.get('adj_efficiency_margin', 'N/A')}
- Adj. Offense: {home_kp.get('adj_offense', 'N/A')} (#{home_kp.get('adj_offense_rank', 'N/A')})
- Adj. Defense: {home_kp.get('adj_defense', 'N/A')} (#{home_kp.get('adj_defense_rank', 'N/A')})
- Adj. Tempo: {home_kp.get('adj_tempo', 'N/A')} (#{home_kp.get('adj_tempo_rank', 'N/A')})
- Strength of Schedule: {home_kp.get('sos_adj_em', 'N/A')}
- Luck: {home_kp.get('luck', 'N/A')}
- Record: {home_kp.get('wins', 0)}-{home_kp.get('losses', 0)}
"""
        if away_kp:
            kenpom_section += f"""
**{away_team}** (KenPom #{away_kp.get('rank', 'N/A')})
- Adj. Efficiency Margin: {away_kp.get('adj_efficiency_margin', 'N/A')}
- Adj. Offense: {away_kp.get('adj_offense', 'N/A')} (#{away_kp.get('adj_offense_rank', 'N/A')})
- Adj. Defense: {away_kp.get('adj_defense', 'N/A')} (#{away_kp.get('adj_defense_rank', 'N/A')})
- Adj. Tempo: {away_kp.get('adj_tempo', 'N/A')} (#{away_kp.get('adj_tempo_rank', 'N/A')})
- Strength of Schedule: {away_kp.get('sos_adj_em', 'N/A')}
- Luck: {away_kp.get('luck', 'N/A')}
- Record: {away_kp.get('wins', 0)}-{away_kp.get('losses', 0)}
"""

    # Haslametrics section
    haslametrics_section = ""
    home_hasla = context.get("home_haslametrics")
    away_hasla = context.get("away_haslametrics")
    if home_hasla or away_hasla:
        haslametrics_section = "\n## HASLAMETRICS ANALYTICS\n"
        if home_hasla:
            haslametrics_section += f"""
**{home_team}** (Haslametrics #{home_hasla.get('rank', 'N/A')})
- All-Play %: {home_hasla.get('all_play_pct', 'N/A')}
- Momentum: {home_hasla.get('momentum_overall', 'N/A')} (O: {home_hasla.get('momentum_offense', 'N/A')}, D: {home_hasla.get('momentum_defense', 'N/A')})
- Last 5: {home_hasla.get('last_5_record', 'N/A')}
- Quadrant Records: Q1: {home_hasla.get('quad_1_record', 'N/A')}, Q2: {home_hasla.get('quad_2_record', 'N/A')}
"""
        if away_hasla:
            haslametrics_section += f"""
**{away_team}** (Haslametrics #{away_hasla.get('rank', 'N/A')})
- All-Play %: {away_hasla.get('all_play_pct', 'N/A')}
- Momentum: {away_hasla.get('momentum_overall', 'N/A')} (O: {away_hasla.get('momentum_offense', 'N/A')}, D: {away_hasla.get('momentum_defense', 'N/A')})
- Last 5: {away_hasla.get('last_5_record', 'N/A')}
- Quadrant Records: Q1: {away_hasla.get('quad_1_record', 'N/A')}, Q2: {away_hasla.get('quad_2_record', 'N/A')}
"""

    prompt = f"""You are an expert NCAA Tournament analyst. For this single-elimination game, provide TWO analyses:
1. BRACKET PICK — which team advances (winner prediction)
2. BETTING RECOMMENDATION — whether there is value on the spread or moneyline

## MATCHUP — {round_display}
**#{away_seed} {away_team}** vs **#{home_seed} {home_team}**
Region: {region}
Date: {context['date']}
Venue: {context['venue'] or 'TBD'} (Neutral site — no home court advantage)

## SEED MATCHUP HISTORY
{seed_history}

## BETTING LINES
Spread: {spread_str or 'Not available'}
Total: O/U {context.get('total') or 'N/A'}
Home ML: {context.get('home_ml') or 'N/A'}
Away ML: {context.get('away_ml') or 'N/A'}
{kenpom_section}{haslametrics_section}
## REQUIRED OUTPUT FORMAT

Respond in JSON format with exactly these fields:
{{
    "picked_team": "home" | "away",
    "pick_confidence": <float 0.0-1.0>,
    "pick_key_factors": [<list of 3-5 key factors for the winner pick>],
    "pick_reasoning": "<2-3 sentence explanation of why this team advances>",
    "recommended_bet": "home_spread" | "away_spread" | "home_ml" | "away_ml" | "over" | "under" | "pass",
    "bet_confidence": <float 0.0-1.0>,
    "bet_key_factors": [<list of 2-4 key factors for the betting recommendation>],
    "bet_reasoning": "<1-2 sentence explanation of the betting value or lack thereof>"
}}

Guidelines:
- "picked_team" MUST be exactly "home" or "away" (home = {home_team}, away = {away_team})
- pick_confidence: 0.5 = coin flip, 0.85+ = very high (appropriate for 1v16)
- For betting: tournament spreads are often inflated for chalk teams — look for underdog value
- If no clear betting edge, set recommended_bet to "pass" and bet_confidence to 0.5
- When KenPom AdjEM difference is <5 points, underdog cover probability rises significantly
- Luck factor (KenPom): high-luck teams regress in single elimination — factor into bet confidence
- Single-elimination variance means upsets happen even when the favorite advances

Respond with ONLY the JSON object, no additional text."""

    return prompt


def analyze_tournament_game(
    game_id: str,
    provider: AIProvider = "claude",
    tournament_id: Optional[str] = None,
) -> dict:
    """
    Run combined AI analysis on a tournament game.

    Fetches tournament-specific context (seeds, region, round) from the
    tournament_bracket view, then calls the AI with a combined prompt that
    returns both a bracket winner pick and a betting recommendation.

    The bracket pick is saved to the bracket_picks table. The betting
    recommendation is returned in the response but not stored separately
    (use /ai-analysis for persistent betting analysis storage).

    Args:
        game_id: UUID of the tournament game
        provider: "claude" or "grok"
        tournament_id: Optional tournament UUID; resolved from the game if not provided

    Returns:
        dict with keys: game_id, ai_provider, tournament_round, region,
        home_seed, away_seed, picked_team, picked_team_id, pick_confidence,
        pick_key_factors, pick_reasoning, recommended_bet, bet_confidence,
        bet_key_factors, bet_reasoning, created_at

    Raises:
        ValueError: If game_id is not a tournament game or provider is invalid
        RuntimeError: If AI call fails after retries
    """
    # 1. Fetch tournament bracket data for this game
    tournament_game = get_tournament_game_data(game_id)
    if not tournament_game:
        raise ValueError(
            f"Game {game_id} not found in tournament_bracket view. "
            "Ensure the game is marked is_tournament=True and seeds are set."
        )

    # 2. Build full game context (KenPom, Haslametrics, spreads, etc.)
    context = build_game_context(game_id)

    # 3. Build tournament-specific metadata
    home_seed = tournament_game.get("home_seed")
    away_seed = tournament_game.get("away_seed")

    # Import seed history helper from bracket_pick_generator
    try:
        from backend.data_collection.bracket_pick_generator import get_seed_matchup_context
    except ImportError:
        from ..data_collection.bracket_pick_generator import get_seed_matchup_context

    matchup_metadata = {
        "home_seed": home_seed,
        "away_seed": away_seed,
        "home_region": tournament_game.get("home_region"),
        "away_region": tournament_game.get("away_region"),
        "tournament_round": tournament_game.get("tournament_round", "unknown"),
        "seed_history": get_seed_matchup_context(home_seed, away_seed),
    }

    # 4. Build combined prompt
    prompt = build_combined_tournament_prompt(context, matchup_metadata)
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]

    # 5. Call AI provider with retries
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
            elif provider == "grok":
                if not grok_client:
                    raise ValueError("Grok API key not configured")
                response = grok_client.chat.completions.create(
                    model="grok-3",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                )
                response_text = response.choices[0].message.content
            else:
                raise ValueError(f"Unknown provider: {provider}")
            break
        except Exception as e:
            last_error = e
            logger.warning(f"Tournament AI analysis attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    if response_text is None:
        raise RuntimeError(
            f"Tournament AI analysis failed after 3 attempts: {_sanitize_error_message(str(last_error))}"
        )

    # 6. Parse combined AI response
    analysis = _extract_json_from_response(response_text)

    picked_side = analysis.get("picked_team", "").lower().strip()
    pick_confidence = min(max(float(analysis.get("pick_confidence", 0.5)), 0.0), 1.0)
    pick_key_factors = analysis.get("pick_key_factors", [])
    pick_reasoning = analysis.get("pick_reasoning", "")

    # 7. Map "home"/"away" to team_id
    full_game = get_game_by_id(game_id)
    if not full_game:
        raise ValueError(f"Game {game_id} not found in games table")

    picked_team_id = None
    picked_team_name = "unknown"

    if picked_side == "home":
        picked_team_id = full_game["home_team_id"]
        picked_team_name = context.get("home_team", "home")
    elif picked_side == "away":
        picked_team_id = full_game["away_team_id"]
        picked_team_name = context.get("away_team", "away")
    else:
        # Fallback: default to the higher seed (lower number)
        if (home_seed or 99) <= (away_seed or 99):
            picked_team_id = full_game["home_team_id"]
            picked_team_name = context.get("home_team", "home")
            picked_side = "home"
        else:
            picked_team_id = full_game["away_team_id"]
            picked_team_name = context.get("away_team", "away")
            picked_side = "away"
        logger.warning(
            f"Tournament AI returned '{analysis.get('picked_team')}' instead of home/away. "
            f"Defaulted to higher seed: {picked_team_name}"
        )

    # 8. Resolve tournament_id if not provided
    if not tournament_id:
        season = tournament_game.get("season")
        if season:
            tournament = get_tournament(season)
            if tournament:
                tournament_id = tournament["id"]

    # 9. Save bracket pick
    reasoning_for_db = pick_reasoning
    if pick_key_factors:
        reasoning_for_db = f"{pick_reasoning} | Key factors: {'; '.join(pick_key_factors[:5])}"

    pick_data = {
        "game_id": game_id,
        "round": matchup_metadata["tournament_round"],
        "region": matchup_metadata.get("home_region") or matchup_metadata.get("away_region"),
        "picked_team_id": picked_team_id,
        "confidence_score": pick_confidence,
        "reasoning": reasoning_for_db[:1000],
    }
    if tournament_id:
        pick_data["tournament_id"] = tournament_id

    saved_pick = upsert_bracket_pick(pick_data)

    import datetime as dt
    created_at = saved_pick.get("created_at") or dt.datetime.now().isoformat()

    return {
        "game_id": game_id,
        "ai_provider": provider,
        "prompt_hash": prompt_hash,
        "tournament_round": matchup_metadata["tournament_round"],
        "region": matchup_metadata.get("home_region") or matchup_metadata.get("away_region"),
        "home_seed": home_seed,
        "away_seed": away_seed,
        "home_team": context.get("home_team"),
        "away_team": context.get("away_team"),
        "picked_team": picked_team_name,
        "picked_team_id": picked_team_id,
        "pick_confidence": pick_confidence,
        "pick_key_factors": pick_key_factors,
        "pick_reasoning": pick_reasoning,
        "recommended_bet": analysis.get("recommended_bet", "pass"),
        "bet_confidence": min(max(float(analysis.get("bet_confidence", 0.5)), 0.0), 1.0),
        "bet_key_factors": analysis.get("bet_key_factors", []),
        "bet_reasoning": analysis.get("bet_reasoning", ""),
        "created_at": created_at,
    }


def analyze_with_claude(context: dict) -> dict:
    """
    Run game analysis using Anthropic's Claude API.

    Calls Claude Sonnet 4 via the Anthropic SDK with a structured betting
    analysis prompt. The prompt includes all available game context (rankings,
    spreads, KenPom, Haslametrics, prediction markets).

    API Call Details:
        - Model: claude-sonnet-4-20250514
        - Max tokens: 1024 (sufficient for JSON response)
        - Single user message with full prompt
        - No system message (role is set in prompt text)

    Response Parsing:
        The raw response text is passed to _extract_json_from_response()
        which handles various AI output formats (raw JSON, code blocks,
        or embedded JSON within prose).

    A prompt hash (MD5, first 16 chars) is stored for deduplication and
    to detect when prompt content changes between analyses.

    Args:
        context: Game context dict from build_game_context()

    Returns:
        Dict with keys: ai_provider, model_used, analysis_type, prompt_hash,
        response, recommended_bet, confidence_score, key_factors, reasoning,
        tokens_used

    Raises:
        ValueError: If ANTHROPIC_API_KEY is not configured
        anthropic.APIError: If the Claude API call fails
    """
    if not claude_client:
        raise ValueError("Claude API key not configured")

    prompt = build_analysis_prompt(context)
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]

    MAX_ATTEMPTS = 3
    BASE_DELAY = 2.0
    MAX_DELAY = 30.0

    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            with claude_breaker:
                response = claude_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
            break
        except CircuitBreakerOpen as e:
            raise  # Don't retry — circuit is open
        except anthropic.RateLimitError as e:
            last_error = e
            # Respect Retry-After header if present; otherwise back off
            retry_after = float(e.response.headers.get("retry-after", BASE_DELAY * (2 ** attempt)))
            sleep_for = min(retry_after, MAX_DELAY)
            logger.warning(
                f"Claude rate limited (attempt {attempt + 1}/{MAX_ATTEMPTS}); "
                f"sleeping {sleep_for:.0f}s"
            )
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(sleep_for)
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
            last_error = e
            logger.warning(f"Claude API attempt {attempt + 1}/{MAX_ATTEMPTS} failed: {e}")
            if attempt < MAX_ATTEMPTS - 1:
                delay = _jitter_delay(attempt, BASE_DELAY, MAX_DELAY)
                time.sleep(delay)
    else:
        raise last_error

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
    """
    Run game analysis using xAI's Grok API.

    Calls Grok-3 via the OpenAI-compatible SDK (base URL: https://api.x.ai/v1).
    Uses the same prompt as Claude for consistent comparison between providers.

    API Call Details:
        - Model: grok-3
        - Max tokens: 1024
        - OpenAI-compatible chat completions endpoint
        - Single user message with full prompt

    Response Parsing:
        Identical to analyze_with_claude() - uses _extract_json_from_response()
        for robust JSON extraction from the AI response text.

    Args:
        context: Game context dict from build_game_context()

    Returns:
        Dict with keys: ai_provider, model_used, analysis_type, prompt_hash,
        response, recommended_bet, confidence_score, key_factors, reasoning,
        tokens_used

    Raises:
        ValueError: If GROK_API_KEY is not configured
        openai.APIError: If the Grok API call fails
    """
    if not grok_client:
        raise ValueError("Grok API key not configured")

    prompt = build_analysis_prompt(context)
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]

    from openai import APITimeoutError, APIConnectionError, RateLimitError as OpenAIRateLimitError

    MAX_ATTEMPTS = 3
    BASE_DELAY = 2.0
    MAX_DELAY = 30.0

    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            with grok_breaker:
                response = grok_client.chat.completions.create(
                    model="grok-3",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1024,
                )
            break
        except CircuitBreakerOpen as e:
            raise  # Don't retry — circuit is open
        except OpenAIRateLimitError as e:
            last_error = e
            retry_after = BASE_DELAY * (2 ** attempt)
            if hasattr(e, "response") and e.response is not None:
                retry_after = float(e.response.headers.get("retry-after", retry_after))
            sleep_for = min(retry_after, MAX_DELAY)
            logger.warning(
                f"Grok rate limited (attempt {attempt + 1}/{MAX_ATTEMPTS}); "
                f"sleeping {sleep_for:.0f}s"
            )
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(sleep_for)
        except (APITimeoutError, APIConnectionError) as e:
            last_error = e
            logger.warning(f"Grok API attempt {attempt + 1}/{MAX_ATTEMPTS} failed: {e}")
            if attempt < MAX_ATTEMPTS - 1:
                delay = _jitter_delay(attempt, BASE_DELAY, MAX_DELAY)
                time.sleep(delay)
    else:
        raise last_error

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


def analyze_game(
    game_id: str,
    provider: AIProvider = "claude",
    save: bool = True,
    fallback_provider: bool = True,
    force: bool = False,
) -> dict:
    """
    Run AI analysis on a game, with a two-level cache hierarchy.

    Cache Strategy (skipped entirely when force=True):
        L1 — In-memory TTLCache (ai_analysis_cache): fast, per-process, 6-hour TTL.
             Prevents redundant AI calls within a single server session.
        L2 — Database (ai_analysis table): persistent, shared across workers.
             Checked when L1 misses; re-populates L1 on hit.
             Only used if the stored analysis is < 6 hours old.
        L3 — Live AI API call: runs only when both caches miss or force=True.

    Args:
        game_id: The game UUID
        provider: Which AI to use ("claude" or "grok")
        save: Whether to save fresh analysis to the database (ignored on cache hits)
        fallback_provider: If True and primary provider fails, try the other provider
        force: If True, bypass all caches and always call the AI API

    Returns:
        Analysis result dict. Includes "from_cache": True when served from L1/L2.
    """
    # ------------------------------------------------------------------
    # L1: In-memory cache
    # ------------------------------------------------------------------
    if not force:
        cached = ai_analysis_cache.get("ai_analysis", game_id=game_id, provider=provider)
        if cached is not None:
            logger.debug(f"Cache L1 HIT: game={game_id} provider={provider}")
            result = dict(cached)
            result["from_cache"] = True
            return result

    # ------------------------------------------------------------------
    # L2: Database cache (ai_analysis table)
    # ------------------------------------------------------------------
    if not force:
        try:
            db_analysis = get_ai_analysis_by_provider(game_id, provider)
            if db_analysis is not None:
                created_at_str = db_analysis.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(
                            created_at_str.replace("Z", "+00:00")
                        )
                        age_seconds = (
                            datetime.now(timezone.utc) - created_at
                        ).total_seconds()
                        if age_seconds < ANALYSIS_CACHE_TTL_SECONDS:
                            logger.info(
                                f"Cache L2 HIT: game={game_id} provider={provider} "
                                f"age={age_seconds/3600:.1f}h"
                            )
                            # Ensure key_factors is a list (Supabase may return JSON string)
                            if isinstance(db_analysis.get("key_factors"), str):
                                try:
                                    db_analysis["key_factors"] = json.loads(
                                        db_analysis["key_factors"]
                                    )
                                except (json.JSONDecodeError, TypeError):
                                    db_analysis["key_factors"] = [db_analysis["key_factors"]]
                            db_analysis["from_cache"] = True
                            # Populate L1 so next request is even faster
                            ai_analysis_cache.set(
                                "ai_analysis",
                                db_analysis,
                                ttl=max(0, int(ANALYSIS_CACHE_TTL_SECONDS - age_seconds)),
                                game_id=game_id,
                                provider=provider,
                            )
                            return db_analysis
                        else:
                            logger.info(
                                f"Cache L2 STALE: game={game_id} provider={provider} "
                                f"age={age_seconds/3600:.1f}h — running fresh analysis"
                            )
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Cache L2: could not parse created_at '{created_at_str}': {e}")
        except Exception as e:
            # Don't let a cache lookup failure block a fresh AI call
            logger.warning(f"Cache L2: DB lookup failed for game={game_id}: {_sanitize_error_message(str(e))}")

    # ------------------------------------------------------------------
    # L3: Live AI API call
    # ------------------------------------------------------------------
    logger.info(f"Cache MISS: calling AI API — game={game_id} provider={provider} force={force}")

    # Build context
    context = build_game_context(game_id)

    # Run analysis with optional failover to the other provider
    primary_error: Optional[Exception] = None
    fallback: Optional[AIProvider] = "grok" if provider == "claude" else "claude"

    if provider == "claude":
        primary_fn = analyze_with_claude
        fallback_fn = analyze_with_grok if fallback_provider else None
        fallback_available = bool(grok_client)
    elif provider == "grok":
        primary_fn = analyze_with_grok
        fallback_fn = analyze_with_claude if fallback_provider else None
        fallback_available = bool(claude_client)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    try:
        analysis = primary_fn(context)
    except CircuitBreakerOpen as e:
        logger.warning(f"Circuit breaker blocked {provider}: {e}")
        primary_error = e
        analysis = None
    except Exception as e:
        logger.error(f"Primary AI provider '{provider}' failed: {_sanitize_error_message(str(e))}")
        primary_error = e
        analysis = None

    if analysis is None and fallback_fn and fallback_available:
        logger.info(f"Falling back to '{fallback}' after '{provider}' failure")
        try:
            analysis = fallback_fn(context)
            # Tag the analysis so callers know it came from the fallback
            analysis["fallback_from"] = provider
        except Exception as fallback_exc:
            logger.error(
                f"Fallback provider '{fallback}' also failed: "
                f"{_sanitize_error_message(str(fallback_exc))}"
            )
            # Re-raise the original error
            raise primary_error from fallback_exc  # type: ignore[misc]

    if analysis is None:
        raise primary_error  # type: ignore[misc]

    # Add game_id to analysis
    analysis["game_id"] = game_id
    analysis["from_cache"] = False

    # Save to database (L2 cache + permanent record)
    if save:
        saved = insert_ai_analysis(analysis)
        analysis["id"] = saved["id"]
        analysis["created_at"] = saved["created_at"]

    # Populate L1 cache so subsequent requests in this process skip the DB lookup
    ai_analysis_cache.set(
        "ai_analysis",
        analysis,
        ttl=ANALYSIS_CACHE_TTL_SECONDS,
        game_id=game_id,
        provider=provider,
    )

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
    """
    Main class for AI analysis with in-memory caching.

    Provides a stateful wrapper around the analyze_game() function,
    adding an in-memory cache to avoid redundant API calls within
    a single server process lifecycle.

    The cache is keyed by "{game_id}:{provider}" and is not shared
    across worker processes or persisted to disk. For persistent
    caching, analyses are stored in the ai_analysis database table.

    Usage:
        analyzer = AIAnalyzer()
        result = analyzer.analyze(game_id, provider="claude")
        both = analyzer.analyze_both(game_id)
    """

    def __init__(self):
        self.cache = {}

    def analyze(
        self,
        game_id: str,
        provider: AIProvider = "claude",
        use_cache: bool = True,
        save: bool = True,
        force: bool = False,
    ) -> dict:
        """
        Analyze a game with optional in-memory caching.

        Delegates to analyze_game() which implements a full L1/L2/L3 cache
        hierarchy. This instance-level dict cache acts as an additional L0
        layer for the lifetime of this AIAnalyzer object.

        Args:
            game_id: UUID of the game to analyze
            provider: AI provider ("claude" or "grok")
            use_cache: If True, check instance-level cache before delegating
            save: If True, persist analysis to database
            force: If True, bypass all caches including L1/L2 in analyze_game()

        Returns:
            Analysis result dict from analyze_game()
        """
        cache_key = f"{game_id}:{provider}"

        if use_cache and not force and cache_key in self.cache:
            return self.cache[cache_key]

        result = analyze_game(game_id, provider, save, force=force)
        self.cache[cache_key] = result

        return result

    def analyze_both(self, game_id: str, save: bool = True) -> dict:
        """
        Run analysis with both Claude and Grok, then compute consensus.

        Calls each available provider sequentially. If both succeed,
        computes a consensus recommendation:
        - If both providers agree on the same non-pass bet, averages
          their confidence scores for a consensus recommendation.
        - If providers disagree, consensus defaults to "pass" with 0.5
          confidence, indicating no clear edge.

        Error handling is per-provider: one provider failing does not
        prevent the other from running. Errors are sanitized via
        _sanitize_error_message() before being included in results.

        Args:
            game_id: UUID of the game to analyze
            save: If True, persist each provider's analysis to database

        Returns:
            Dict with keys "claude", "grok", and "consensus" (when both
            providers succeed). May include "claude_error" or "grok_error"
            if a provider fails.
        """
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
