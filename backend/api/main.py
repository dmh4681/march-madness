"""
Conference Contrarian API

FastAPI backend for serving predictions.
Only deploy after edge validates and model shows positive ROI.

Usage:
    uvicorn main:app --reload
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Conference Contrarian API",
    description="NCAA basketball betting edge analyzer",
    version="0.1.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class GamePredictionRequest(BaseModel):
    favorite_team: str
    underdog_team: str
    favorite_rank: int
    is_home_underdog: bool = False
    spread: Optional[float] = None


class GamePrediction(BaseModel):
    favorite_team: str
    underdog_team: str
    cover_probability: float
    confidence: str
    recommendation: str
    edge_pct: float
    kelly_fraction: Optional[float] = None


class TrackRecord(BaseModel):
    total_predictions: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    roi: float
    period: str


# Endpoints
@app.get("/")
def root():
    """Health check."""
    return {
        "message": "Conference Contrarian API",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model_loaded": False,  # TODO: Check if model file exists
    }


@app.post("/predict", response_model=GamePrediction)
def predict_game(request: GamePredictionRequest):
    """
    Get prediction for a single game.

    POST /predict
    {
        "favorite_team": "Duke",
        "underdog_team": "NC State",
        "favorite_rank": 8,
        "is_home_underdog": true
    }
    """
    # TODO: Load model and make real prediction
    # For now, return placeholder

    # Validate rank
    if request.favorite_rank < 1 or request.favorite_rank > 25:
        raise HTTPException(status_code=400, detail="Favorite rank must be 1-25")

    # Placeholder prediction logic
    # Higher rank = weaker favorite = better for underdog
    base_prob = 0.45 + (request.favorite_rank - 1) * 0.01
    if request.is_home_underdog:
        base_prob += 0.03

    # Clamp to reasonable range
    prob = min(0.70, max(0.35, base_prob))

    # Determine recommendation
    if prob >= 0.60:
        recommendation = "BET"
        confidence = "HIGH"
    elif prob >= 0.55:
        recommendation = "LEAN"
        confidence = "MEDIUM"
    else:
        recommendation = "PASS"
        confidence = "LOW"

    return GamePrediction(
        favorite_team=request.favorite_team,
        underdog_team=request.underdog_team,
        cover_probability=prob,
        confidence=confidence,
        recommendation=recommendation,
        edge_pct=prob - 0.524,
        kelly_fraction=max(0, (prob * 0.91 - (1 - prob)) / 0.91) * 0.25 if prob > 0.52 else None,
    )


@app.get("/today")
def get_todays_plays():
    """
    Get today's recommended plays.

    Returns list of games with model predictions, sorted by edge.
    """
    # TODO: Fetch today's games and run predictions
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "games": [],
        "message": "No games scraped yet. Run data collection first.",
    }


@app.get("/stats", response_model=TrackRecord)
def get_track_record():
    """
    Get model's historical performance.

    Returns win rate, ROI, and prediction counts.
    """
    # TODO: Calculate from predictions table
    return TrackRecord(
        total_predictions=0,
        wins=0,
        losses=0,
        pushes=0,
        win_rate=0.0,
        roi=0.0,
        period="all-time",
    )


@app.get("/game/{game_id}")
def get_game_analysis(game_id: str):
    """
    Get detailed analysis for a specific game.
    """
    # TODO: Look up game and return analysis
    raise HTTPException(status_code=404, detail="Game not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
