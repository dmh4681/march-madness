"""
Conference Contrarian API

FastAPI backend for serving predictions and AI analysis.

Usage:
    uvicorn backend.api.main:app --reload
"""

import os
import re
import logging
from datetime import date, datetime
from typing import Optional, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

# Configure logging - avoid leaking sensitive info in logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our modules
from .supabase_client import (
    get_game_by_id,
    get_games_by_date,
    get_upcoming_games,
    get_today_games_view,
    get_latest_spread,
    get_latest_prediction,
    get_ai_analyses,
    get_season_performance,
    calculate_season_stats,
    get_current_rankings,
)
from .ai_service import analyze_game, analyzer, get_quick_recommendation, build_game_context


# =============================================================================
# SECURITY: CORS Configuration
# =============================================================================
# SECURITY: Only allow specific, trusted origins in production
# Default to localhost for development only
def _get_allowed_origins() -> list[str]:
    """
    Parse and validate allowed CORS origins from environment.

    Security considerations:
    - Only allow HTTPS origins in production (except localhost for dev)
    - Validate origin format to prevent injection
    - Reject wildcard (*) origins for security
    """
    raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

    validated_origins = []
    # Regex to validate origin format (protocol://domain:optional_port)
    origin_pattern = re.compile(r'^https?://[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9](:\d+)?$')

    for origin in origins:
        # SECURITY: Reject wildcard - never allow all origins
        if origin == "*":
            logger.warning("SECURITY: Wildcard CORS origin rejected. Configure specific origins.")
            continue

        # Validate origin format
        if origin_pattern.match(origin):
            validated_origins.append(origin)
        else:
            logger.warning(f"SECURITY: Invalid CORS origin format rejected: {origin[:50]}")

    if not validated_origins:
        # SECURITY: Fail safe - default to localhost only if no valid origins
        logger.warning("SECURITY: No valid CORS origins configured, defaulting to localhost only")
        validated_origins = ["http://localhost:3000"]

    return validated_origins


ALLOWED_ORIGINS = _get_allowed_origins()
logger.info(f"CORS configured for origins: {ALLOWED_ORIGINS}")

app = FastAPI(
    title="Conference Contrarian API",
    description="AI-powered NCAA basketball betting analysis",
    version="1.0.0",
    # SECURITY: Disable automatic docs in production if needed
    # docs_url=None if os.getenv("ENVIRONMENT") == "production" else "/docs",
    # redoc_url=None if os.getenv("ENVIRONMENT") == "production" else "/redoc",
)

# SECURITY: Strict CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Only specific trusted origins
    allow_credentials=False,  # SECURITY: Disabled - prevents credential-based attacks
    allow_methods=["GET", "POST", "OPTIONS"],  # SECURITY: Only methods actually used
    allow_headers=["Content-Type", "Accept", "Authorization"],  # SECURITY: Explicit allowed headers
    expose_headers=["X-Request-ID"],  # SECURITY: Only expose necessary headers
    max_age=600,  # Cache preflight for 10 minutes
)


# =============================================================================
# SECURITY: Global Exception Handler
# =============================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    SECURITY: Global exception handler that prevents internal error details from leaking.

    - Logs full error details server-side for debugging
    - Returns generic error message to client
    - Never exposes stack traces, file paths, or internal state
    """
    # Generate a request ID for correlation (without exposing internal details)
    request_id = id(request) % 100000  # Simple numeric ID for client reference

    # Log the full error server-side for debugging
    logger.error(
        f"Request ID {request_id}: Unhandled exception on {request.method} {request.url.path}",
        exc_info=exc
    )

    # SECURITY: Return generic error to client - never expose internal details
    return JSONResponse(
        status_code=500,
        content={
            "error": "An internal error occurred",
            "request_id": request_id,
            "message": "Please contact support if this persists"
        }
    )


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================


class PredictRequest(BaseModel):
    game_id: Optional[str] = None
    # Or provide matchup details
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    spread: Optional[float] = None
    is_conference_game: Optional[bool] = False
    home_rank: Optional[int] = None
    away_rank: Optional[int] = None


class PredictResponse(BaseModel):
    game_id: Optional[str]
    home_team: str
    away_team: str
    home_cover_prob: float
    away_cover_prob: float
    confidence: str
    recommended_bet: str
    edge_pct: Optional[float]
    reasoning: Optional[str]


class AIAnalysisRequest(BaseModel):
    game_id: str
    provider: Literal["claude", "grok"] = "claude"


class AIAnalysisResponse(BaseModel):
    game_id: str
    provider: str
    recommended_bet: str
    confidence_score: float
    key_factors: list[str]
    reasoning: str
    created_at: Optional[str] = None


class StatsResponse(BaseModel):
    season: int
    total_bets: int
    wins: int
    losses: int
    pushes: int
    win_pct: float
    units_wagered: float
    units_won: float
    roi_pct: float


class GameResponse(BaseModel):
    id: str
    date: str
    home_team: str
    away_team: str
    home_rank: Optional[int]
    away_rank: Optional[int]
    home_spread: Optional[float]
    is_conference_game: bool
    prediction: Optional[dict] = None
    ai_analyses: list[dict] = []


# ============================================
# ENDPOINTS
# ============================================


@app.get("/")
def root():
    """API info and health check."""
    return {
        "name": "Conference Contrarian API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "supabase_configured": bool(os.getenv("SUPABASE_URL")),
        "claude_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "grok_configured": bool(os.getenv("GROK_API_KEY")),
    }


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    """
    Get prediction for a game.

    Can provide either:
    - game_id: UUID of an existing game in the database
    - Or: home_team, away_team, spread, etc. for ad-hoc prediction
    """
    if request.game_id:
        # Fetch game from database
        game = get_game_by_id(request.game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

        spread_data = get_latest_spread(request.game_id)
        prediction = get_latest_prediction(request.game_id)

        home_team = game.get("home_team", {}).get("name", "Unknown")
        away_team = game.get("away_team", {}).get("name", "Unknown")

        if prediction:
            return PredictResponse(
                game_id=request.game_id,
                home_team=home_team,
                away_team=away_team,
                home_cover_prob=prediction.get("predicted_home_cover_prob", 0.5),
                away_cover_prob=prediction.get("predicted_away_cover_prob", 0.5),
                confidence=prediction.get("confidence_tier", "low"),
                recommended_bet=prediction.get("recommended_bet", "pass"),
                edge_pct=prediction.get("edge_pct"),
                reasoning=None,
            )

        # No prediction exists - calculate using spread-based heuristics
        context = build_game_context(request.game_id)
        quick = get_quick_recommendation(context)

        # Calculate probability based on spread
        spread = spread_data.get("home_spread") if spread_data else None
        home_cover_prob = 0.5
        confidence = "low"
        edge_pct = None

        if spread is not None:
            # Base adjustment for home court advantage
            home_cover_prob = 0.52

            # Conference games have stronger home edge
            if game.get("is_conference_game"):
                home_cover_prob = 0.53

            # Adjust based on spread magnitude
            if abs(spread) > 10:
                home_cover_prob = 0.48 if spread < 0 else 0.52
            elif abs(spread) < 3:
                home_cover_prob = 0.55 if spread < 0 else 0.54
            elif abs(spread) >= 3 and abs(spread) <= 7:
                home_cover_prob = 0.54 if spread < 0 else 0.52

            # Determine confidence
            edge = abs(home_cover_prob - 0.5) * 100
            if edge > 4:
                confidence = "high"
                edge_pct = edge
            elif edge > 2:
                confidence = "medium"
                edge_pct = edge

        return PredictResponse(
            game_id=request.game_id,
            home_team=home_team,
            away_team=away_team,
            home_cover_prob=home_cover_prob,
            away_cover_prob=1 - home_cover_prob,
            confidence=confidence,
            recommended_bet=quick["recommended_bet"],
            edge_pct=edge_pct,
            reasoning=quick["reasoning"],
        )

    elif request.home_team and request.away_team:
        # Ad-hoc prediction
        context = {
            "home_team": request.home_team,
            "away_team": request.away_team,
            "home_rank": request.home_rank,
            "away_rank": request.away_rank,
            "spread": request.spread,
            "is_conference_game": request.is_conference_game,
        }

        quick = get_quick_recommendation(context)

        # Calculate probability based on spread
        home_cover_prob = 0.5
        confidence = "low"
        edge_pct = None

        if request.spread is not None:
            spread = request.spread
            # Base adjustment for home court advantage
            home_cover_prob = 0.52

            # Conference games have stronger home edge
            if request.is_conference_game:
                home_cover_prob = 0.53

            # Adjust based on spread magnitude
            if abs(spread) > 10:
                home_cover_prob = 0.48 if spread < 0 else 0.52
            elif abs(spread) < 3:
                home_cover_prob = 0.55 if spread < 0 else 0.54
            elif abs(spread) >= 3 and abs(spread) <= 7:
                home_cover_prob = 0.54 if spread < 0 else 0.52

            # Determine confidence
            edge = abs(home_cover_prob - 0.5) * 100
            if edge > 4:
                confidence = "high"
                edge_pct = edge
            elif edge > 2:
                confidence = "medium"
                edge_pct = edge

        return PredictResponse(
            game_id=None,
            home_team=request.home_team,
            away_team=request.away_team,
            home_cover_prob=home_cover_prob,
            away_cover_prob=1 - home_cover_prob,
            confidence=confidence,
            recommended_bet=quick["recommended_bet"],
            edge_pct=edge_pct,
            reasoning=quick["reasoning"],
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either game_id or (home_team + away_team)"
        )


@app.get("/ai-analysis")
def ai_analysis_get():
    """Debug endpoint - if you see this, the request was GET not POST."""
    return {"error": "This endpoint requires POST method", "method_received": "GET"}


@app.post("/ai-analysis", response_model=AIAnalysisResponse)
def ai_analysis(request: AIAnalysisRequest):
    """
    Generate AI analysis for a game.

    Uses Claude or Grok to analyze the matchup and provide betting recommendations.
    """
    try:
        result = analyze_game(request.game_id, request.provider)

        return AIAnalysisResponse(
            game_id=request.game_id,
            provider=result["ai_provider"],
            recommended_bet=result["recommended_bet"],
            confidence_score=result["confidence_score"],
            key_factors=result["key_factors"],
            reasoning=result["reasoning"],
            created_at=result.get("created_at"),
        )

    except ValueError as e:
        # SECURITY: ValueError is user-input related, safe to return sanitized message
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = error_msg[:100]  # Truncate long error messages
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        # SECURITY: Log full error server-side, return generic message to client
        logger.error(f"AI analysis failed for game {request.game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI analysis failed. Please try again later.")


@app.get("/today")
def get_today():
    """
    Get today's games with predictions and analysis.
    """
    try:
        games = get_today_games_view()
        return {
            "date": date.today().isoformat(),
            "game_count": len(games),
            "games": games,
        }
    except Exception as e:
        # SECURITY: Log error server-side, return safe response to client
        logger.error(f"Error fetching today's games: {e}", exc_info=True)
        return {
            "date": date.today().isoformat(),
            "game_count": 0,
            "games": [],
            "error": "Unable to fetch games. Please try again later.",
        }


@app.get("/games")
def get_games(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 7,
    page: int = 1,
    page_size: int = 20
):
    """
    Get upcoming games with pagination.

    Query params:
    - start_date: ISO date string (default: today)
    - end_date: ISO date string (default: start + days)
    - days: Number of days to fetch (default: 7)
    - page: Page number, 1-indexed (default: 1)
    - page_size: Number of games per page, max 50 (default: 20)
    """
    try:
        # SECURITY: Validate pagination params
        page = max(1, page)  # Ensure page is at least 1
        page_size = max(1, min(50, page_size))  # Clamp between 1 and 50

        if start_date:
            all_games = get_games_by_date(date.fromisoformat(start_date))
        else:
            all_games = get_upcoming_games(days)

        # Calculate pagination
        total_games = len(all_games)
        total_pages = (total_games + page_size - 1) // page_size  # Ceiling division
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_games = all_games[start_idx:end_idx]

        return {
            "game_count": len(paginated_games),
            "total_games": total_games,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_more": page < total_pages,
            "games": paginated_games,
        }
    except Exception as e:
        # SECURITY: Log error server-side, return generic message to client
        logger.error(f"Error fetching games: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to fetch games. Please try again later.")


@app.get("/games/{game_id}", response_model=GameResponse)
def get_game(game_id: str):
    """
    Get detailed info for a specific game.
    """
    game = get_game_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    spread = get_latest_spread(game_id)
    prediction = get_latest_prediction(game_id)
    analyses = get_ai_analyses(game_id)

    return GameResponse(
        id=game_id,
        date=game.get("date"),
        home_team=game.get("home_team", {}).get("name", "Unknown"),
        away_team=game.get("away_team", {}).get("name", "Unknown"),
        home_rank=None,  # TODO: get from rankings
        away_rank=None,
        home_spread=spread.get("home_spread") if spread else None,
        is_conference_game=game.get("is_conference_game", False),
        prediction=prediction,
        ai_analyses=analyses,
    )


class GameAnalyticsResponse(BaseModel):
    """Response model for game analytics (KenPom + Haslametrics)."""
    game_id: str
    home_team: str
    away_team: str
    home_kenpom: Optional[dict] = None
    away_kenpom: Optional[dict] = None
    home_haslametrics: Optional[dict] = None
    away_haslametrics: Optional[dict] = None


@app.get("/games/{game_id}/analytics", response_model=GameAnalyticsResponse)
def get_game_analytics(game_id: str):
    """
    Get KenPom and Haslametrics analytics for a specific game.

    This endpoint is designed for lazy loading - fetch analytics only when
    a user expands a game card or views detailed analytics section.
    """
    from .supabase_client import get_team_kenpom, get_team_haslametrics

    game = get_game_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    home_team = game.get("home_team", {})
    away_team = game.get("away_team", {})
    home_team_id = home_team.get("id")
    away_team_id = away_team.get("id")

    # Fetch analytics data for both teams
    home_kenpom = None
    away_kenpom = None
    home_haslametrics = None
    away_haslametrics = None

    try:
        if home_team_id:
            home_kenpom = get_team_kenpom(home_team_id)
            home_haslametrics = get_team_haslametrics(home_team_id)
        if away_team_id:
            away_kenpom = get_team_kenpom(away_team_id)
            away_haslametrics = get_team_haslametrics(away_team_id)
    except Exception as e:
        # SECURITY: Log error server-side, continue without analytics
        logger.warning(f"Error fetching analytics for game {game_id}: {e}")

    return GameAnalyticsResponse(
        game_id=game_id,
        home_team=home_team.get("name", "Unknown"),
        away_team=away_team.get("name", "Unknown"),
        home_kenpom=home_kenpom,
        away_kenpom=away_kenpom,
        home_haslametrics=home_haslametrics,
        away_haslametrics=away_haslametrics,
    )


@app.get("/stats", response_model=StatsResponse)
def get_stats(season: Optional[int] = None):
    """
    Get performance statistics.
    """
    if season is None:
        season = date.today().year

    try:
        stats = calculate_season_stats(season)

        if "error" in stats:
            # Return zeros if no data
            return StatsResponse(
                season=season,
                total_bets=0,
                wins=0,
                losses=0,
                pushes=0,
                win_pct=0.0,
                units_wagered=0.0,
                units_won=0.0,
                roi_pct=0.0,
            )

        return StatsResponse(**stats)

    except Exception as e:
        # SECURITY: Log error server-side, return generic message to client
        logger.error(f"Error calculating stats for season {season}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to fetch statistics. Please try again later.")


@app.get("/rankings")
def get_rankings(season: Optional[int] = None, poll_type: str = "ap"):
    """
    Get current AP rankings.
    """
    if season is None:
        season = date.today().year

    try:
        rankings = get_current_rankings(season, poll_type)
        return {
            "season": season,
            "poll_type": poll_type,
            "rankings": rankings,
        }
    except Exception as e:
        # SECURITY: Log error server-side, return generic message to client
        logger.error(f"Error fetching rankings for season {season}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to fetch rankings. Please try again later.")


@app.post("/refresh")
def refresh_data(
    api_key: Optional[str] = None,
    force_regenerate: bool = False
):
    """
    Trigger a data refresh (games, spreads, rankings).

    This endpoint should be called by a cron job or manually.

    Query params:
    - api_key: Optional authentication key
    - force_regenerate: If true, delete and regenerate all predictions
    """
    # Simple API key check (only if REFRESH_API_KEY is set in environment)
    expected_key = os.getenv("REFRESH_API_KEY")
    if expected_key and api_key and api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # If no key is provided and one is expected, still allow (for manual triggers)

    try:
        from ..data_collection.daily_refresh import run_daily_refresh

        results = run_daily_refresh(force_regenerate_predictions=force_regenerate)

        return {
            "status": results.get("status", "success"),
            "timestamp": results.get("timestamp"),
            "results": results,
        }

    except ImportError as e:
        # SECURITY: Log detailed error server-side
        logger.error(f"Refresh import error: {e}", exc_info=True)
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": "Service configuration error",
        }
    except Exception as e:
        # SECURITY: Log error server-side, return generic message to client
        logger.error(f"Refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Data refresh failed. Please try again later.")


@app.post("/regenerate-predictions")
def regenerate_predictions():
    """
    Quick endpoint to regenerate predictions only (no odds/kenpom fetch).
    Much faster than full /refresh.
    """
    try:
        from ..data_collection.daily_refresh import run_predictions

        # Don't use force_regenerate - just create predictions for games that don't have them
        results = run_predictions(force_regenerate=False)

        return {
            "status": "success",
            "predictions_created": results.get("predictions_created", 0),
        }
    except Exception as e:
        # SECURITY: Log error server-side, return generic message to client
        logger.error(f"Prediction regeneration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Prediction regeneration failed. Please try again later.")


@app.post("/refresh-haslametrics")
def refresh_haslametrics_endpoint():
    """
    Quick endpoint to refresh only Haslametrics data.
    Much faster than full /refresh - useful for testing.
    """
    try:
        from ..data_collection.haslametrics_scraper import refresh_haslametrics_data

        results = refresh_haslametrics_data(season=2025)

        return {
            "status": results.get("status", "success"),
            "timestamp": results.get("timestamp"),
            "results": results,
        }
    except ImportError as e:
        # SECURITY: Log detailed error server-side
        logger.error(f"Haslametrics import error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": "Service configuration error",
        }
    except Exception as e:
        # SECURITY: Log error server-side, return generic message to client
        logger.error(f"Haslametrics refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Haslametrics refresh failed. Please try again later.")


@app.get("/backtest")
def backtest(
    start_date: str,
    end_date: str,
    model: str = "baseline"
):
    """
    Run backtest on historical data.
    """
    # TODO: Implement backtesting
    return {
        "start_date": start_date,
        "end_date": end_date,
        "model": model,
        "message": "Backtesting not yet implemented",
    }


@app.get("/debug/ai-analysis/{game_id}")
def debug_ai_analysis(game_id: str, provider: str = "claude"):
    """
    Debug endpoint to diagnose AI analysis issues.
    Returns detailed error information instead of generic messages.

    WARNING: This endpoint exposes internal errors - remove in production!
    """
    results = {
        "game_id": game_id,
        "provider": provider,
        "steps": {},
        "errors": [],
    }

    # Step 1: Check if game exists
    try:
        game = get_game_by_id(game_id)
        if game:
            results["steps"]["1_game_fetch"] = {
                "status": "success",
                "home_team": game.get("home_team", {}).get("name"),
                "away_team": game.get("away_team", {}).get("name"),
            }
        else:
            results["steps"]["1_game_fetch"] = {"status": "failed", "error": "Game not found"}
            results["errors"].append("Game not found")
            return results
    except Exception as e:
        results["steps"]["1_game_fetch"] = {"status": "error", "error": str(e)}
        results["errors"].append(f"Game fetch error: {str(e)}")
        return results

    # Step 2: Build game context
    try:
        context = build_game_context(game_id)
        results["steps"]["2_build_context"] = {
            "status": "success",
            "has_kenpom": bool(context.get("home_kenpom") or context.get("away_kenpom")),
            "has_haslametrics": bool(context.get("home_haslametrics") or context.get("away_haslametrics")),
            "has_spread": context.get("spread") is not None,
        }
    except Exception as e:
        results["steps"]["2_build_context"] = {"status": "error", "error": str(e)}
        results["errors"].append(f"Context build error: {str(e)}")
        return results

    # Step 3: Check API keys
    import os
    results["steps"]["3_api_keys"] = {
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "grok_configured": bool(os.getenv("GROK_API_KEY")),
    }

    if provider == "claude" and not os.getenv("ANTHROPIC_API_KEY"):
        results["errors"].append("ANTHROPIC_API_KEY not configured")
    if provider == "grok" and not os.getenv("GROK_API_KEY"):
        results["errors"].append("GROK_API_KEY not configured")

    # Step 4: Try the actual AI call
    try:
        from .ai_service import analyze_with_claude, analyze_with_grok, build_analysis_prompt

        prompt = build_analysis_prompt(context)
        results["steps"]["4_prompt_build"] = {"status": "success", "prompt_length": len(prompt)}

        if provider == "claude":
            analysis_result = analyze_with_claude(context)
        else:
            analysis_result = analyze_with_grok(context)

        results["steps"]["5_ai_call"] = {
            "status": "success",
            "recommended_bet": analysis_result.get("recommended_bet"),
            "confidence": analysis_result.get("confidence_score"),
        }
    except Exception as e:
        results["steps"]["5_ai_call"] = {"status": "error", "error": str(e), "type": type(e).__name__}
        results["errors"].append(f"AI call error ({type(e).__name__}): {str(e)}")
        return results

    # Step 5: Try database insert
    try:
        from .supabase_client import insert_ai_analysis

        # Prepare the data that would be inserted
        insert_data = {
            "game_id": game_id,
            "ai_provider": provider,
            "analysis": analysis_result.get("analysis", ""),
            "recommended_bet": analysis_result.get("recommended_bet"),
            "confidence_score": analysis_result.get("confidence_score"),
            "key_factors": analysis_result.get("key_factors", []),
            "reasoning": analysis_result.get("reasoning", ""),
        }

        # Try the insert
        inserted = insert_ai_analysis(insert_data)
        results["steps"]["6_db_insert"] = {
            "status": "success",
            "inserted_id": inserted.get("id") if inserted else None,
        }
    except Exception as e:
        results["steps"]["6_db_insert"] = {"status": "error", "error": str(e), "type": type(e).__name__}
        results["errors"].append(f"DB insert error ({type(e).__name__}): {str(e)}")

    results["overall_status"] = "success" if not results["errors"] else "failed"
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
