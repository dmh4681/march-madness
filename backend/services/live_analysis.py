"""
Live Analysis Service
=====================

Generates AI-powered explanations for significant odds movements
using the existing ai_service module. Does not modify existing
AI analysis logic -- only adds movement-specific re-analysis.
"""

import logging
from typing import Optional

from backend.api.ai_service import (
    claude_client,
    _extract_json_from_response,
    _sanitize_error_message,
    build_game_context,
)

logger = logging.getLogger(__name__)


def generate_movement_analysis(game_id: str, movement: dict) -> dict:
    """
    Generate AI analysis explaining a significant odds movement.

    Uses Claude to interpret why odds moved and whether the updated
    line creates new value. Does NOT save to database or modify
    existing analyses.

    Args:
        game_id: UUID of the game
        movement: Movement dict from OddsMonitor

    Returns:
        Dict with explanation, updated_recommendation, confidence, and action
    """
    if not claude_client:
        return {
            "status": "error",
            "message": "Claude API not configured",
        }

    try:
        context = build_game_context(game_id)
    except ValueError as e:
        return {
            "status": "error",
            "message": _sanitize_error_message(str(e)),
        }

    spread_mv = movement.get("spread_movement")
    prob_mv = movement.get("home_prob_movement")

    prompt = f"""You are an expert college basketball betting analyst. A significant odds movement has been detected for the following game. Analyze the movement and provide updated recommendations.

## GAME
**{movement.get('away_team', 'Away')}** @ **{movement.get('home_team', 'Home')}**

## ODDS MOVEMENT
- Previous spread: {movement.get('previous_spread', 'N/A')}
- Current spread: {movement.get('current_spread', 'N/A')}
- Spread movement: {f"{spread_mv:+.1f} points" if spread_mv is not None else "N/A"}
- Previous home ML: {movement.get('previous_home_ml', 'N/A')}
- Current home ML: {movement.get('current_home_ml', 'N/A')}
- Implied probability shift: {f"{prob_mv*100:+.1f}%" if prob_mv is not None else "N/A"}

## YOUR TASK
1. Explain the most likely reason for this line movement
2. Assess whether the NEW line offers better or worse value
3. Provide an updated recommendation based on the movement

## REQUIRED OUTPUT FORMAT
Respond in JSON format:
{{
    "explanation": "<2-3 sentences explaining the likely cause of movement>",
    "updated_recommendation": "home_spread" | "away_spread" | "home_ml" | "away_ml" | "over" | "under" | "pass",
    "confidence": <float 0.0-1.0>,
    "action": "new_value" | "hold" | "fade" | "pass"
}}

Action meanings:
- "new_value": The movement created new betting value
- "hold": Original recommendation still valid
- "fade": Movement went too far, opposite side has value
- "pass": No clear edge at the new line

Respond with ONLY the JSON object."""

    try:
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text
        analysis = _extract_json_from_response(response_text)

        return {
            "status": "success",
            "game_id": game_id,
            "movement": movement,
            "explanation": analysis.get("explanation", ""),
            "updated_recommendation": analysis.get("updated_recommendation", "pass"),
            "confidence": analysis.get("confidence", 0.5),
            "action": analysis.get("action", "pass"),
            "raw_response": response_text,
        }

    except Exception as e:
        logger.error(f"Movement analysis failed for game {game_id}: {e}")
        return {
            "status": "error",
            "game_id": game_id,
            "message": _sanitize_error_message(str(e)),
        }
