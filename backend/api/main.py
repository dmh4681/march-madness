"""
Conference Contrarian API

FastAPI backend for serving predictions and AI analysis.

Usage:
    uvicorn backend.api.main:app --reload
"""

import os
from datetime import date, datetime
from typing import Optional, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

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

app = FastAPI(
    title="Conference Contrarian API",
    description="AI-powered NCAA basketball betting analysis",
    version="1.0.0",
)

# CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
# Clean up any whitespace from env var parsing
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # Disable credentials to allow simpler CORS
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cache preflight for 10 minutes
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


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
        # Return empty if database not configured
        return {
            "date": date.today().isoformat(),
            "game_count": 0,
            "games": [],
            "error": str(e),
        }


@app.get("/games")
def get_games(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 7
):
    """
    Get upcoming games.

    Query params:
    - start_date: ISO date string (default: today)
    - end_date: ISO date string (default: start + days)
    - days: Number of days to fetch (default: 7)
    """
    try:
        if start_date:
            games = get_games_by_date(date.fromisoformat(start_date))
        else:
            games = get_upcoming_games(days)

        return {
            "game_count": len(games),
            "games": games,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": f"Import error: {str(e)}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")


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
        return {
            "status": "error",
            "error": f"Import error: {str(e)}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Haslametrics refresh failed: {str(e)}")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
