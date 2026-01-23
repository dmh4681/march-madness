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
from typing import Optional, Literal, Annotated

# Timezone handling - display dates in US Eastern time
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Fallback

EASTERN_TZ = ZoneInfo("America/New_York")


def get_eastern_date_today() -> date:
    """Get today's date in US Eastern time for consistent display."""
    return datetime.now(EASTERN_TZ).date()

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator, model_validator

load_dotenv()

# Import our middleware
from .middleware import (
    RequestLoggingMiddleware,
    ApiException,
    ValidationException,
    NotFoundException,
    ExternalApiException,
    api_exception_handler,
    validation_exception_handler,
    general_exception_handler,
    success_response,
    error_response,
    # Rate limiting
    limiter,
    rate_limit_exceeded_handler,
    RATE_LIMIT_AI_ENDPOINTS,
    RATE_LIMIT_STANDARD_ENDPOINTS,
)
from slowapi.errors import RateLimitExceeded

# Import secrets validator
from .secrets_validator import (
    validate_all_secrets,
    log_secrets_status,
    get_secrets_status,
    check_ai_provider_available,
    SecretsValidationError,
)

# Configure logging - avoid leaking sensitive info in logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY: Startup Secrets Validation
# =============================================================================
# Validate all secrets at startup and log status (never actual values)
try:
    _secrets_validation = validate_all_secrets(raise_on_missing_required=False)
    log_secrets_status()

    if not _secrets_validation.is_valid:
        logger.error(
            "SECURITY WARNING: Required secrets are missing. "
            f"Missing: {_secrets_validation.missing_required}. "
            "The application may not function correctly."
        )
except SecretsValidationError as e:
    logger.error(f"CRITICAL: Secrets validation failed: {e}")
    # Don't exit - let the app start so health checks can report the issue

# Import our modules
from .supabase_client import (
    get_game_by_id,
    get_games_by_date,
    get_upcoming_games,
    get_upcoming_games_view,
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

# =============================================================================
# SECURITY: Rate Limiting Setup
# =============================================================================
# Add the rate limiter to app state (required by slowapi)
app.state.limiter = limiter

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
# SECURITY: Middleware & Exception Handlers
# =============================================================================

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Register exception handlers
app.add_exception_handler(ApiException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(Exception, general_exception_handler)


# ============================================
# VALIDATION HELPERS
# ============================================

UUID_PATTERN = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)


def validate_uuid(value: str, field_name: str = "id") -> str:
    """Validate UUID format."""
    if not UUID_PATTERN.match(value):
        raise ValidationException(
            message=f"Invalid {field_name} format",
            details={"field": field_name, "expected": "UUID format (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"}
        )
    return value


def validate_date_string(value: str, field_name: str = "date") -> date:
    """Validate and parse ISO date string."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationException(
            message=f"Invalid {field_name} format",
            details={"field": field_name, "expected": "ISO date format (YYYY-MM-DD)"}
        )


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================


class PredictRequest(BaseModel):
    """Request model for prediction endpoint."""
    game_id: Optional[str] = Field(
        default=None,
        description="UUID of existing game in database"
    )
    # Or provide matchup details
    home_team: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Home team name"
    )
    away_team: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Away team name"
    )
    spread: Optional[float] = Field(
        default=None,
        ge=-50.0,
        le=50.0,
        description="Point spread (home team perspective)"
    )
    is_conference_game: Optional[bool] = Field(default=False)
    home_rank: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Home team AP ranking"
    )
    away_rank: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Away team AP ranking"
    )

    @field_validator('game_id')
    @classmethod
    def validate_game_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not UUID_PATTERN.match(v):
            raise ValueError('game_id must be a valid UUID')
        return v

    @model_validator(mode='after')
    def check_required_fields(self):
        """Ensure either game_id or team names are provided."""
        if not self.game_id and not (self.home_team and self.away_team):
            raise ValueError('Must provide either game_id or (home_team + away_team)')
        return self


class PredictResponse(BaseModel):
    """Response model for prediction endpoint."""
    game_id: Optional[str]
    home_team: str
    away_team: str
    home_cover_prob: float = Field(ge=0.0, le=1.0)
    away_cover_prob: float = Field(ge=0.0, le=1.0)
    confidence: str
    recommended_bet: str
    edge_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    reasoning: Optional[str]


class AIAnalysisRequest(BaseModel):
    """Request model for AI analysis endpoint."""
    game_id: str = Field(
        ...,
        description="UUID of game to analyze"
    )
    provider: Literal["claude", "grok"] = Field(
        default="claude",
        description="AI provider to use for analysis"
    )

    @field_validator('game_id')
    @classmethod
    def validate_game_id(cls, v: str) -> str:
        if not UUID_PATTERN.match(v):
            raise ValueError('game_id must be a valid UUID')
        return v


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
    """Response model for game detail endpoint."""
    id: str
    date: str
    home_team: str
    away_team: str
    home_rank: Optional[int] = Field(default=None, ge=1, le=100)
    away_rank: Optional[int] = Field(default=None, ge=1, le=100)
    home_spread: Optional[float] = Field(default=None, ge=-50.0, le=50.0)
    is_conference_game: bool
    prediction: Optional[dict] = None
    ai_analyses: list[dict] = []


# ============================================
# QUERY PARAMETER MODELS
# ============================================

class GamesQueryParams(BaseModel):
    """Query parameters for /games endpoint."""
    start_date: Optional[str] = Field(
        default=None,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Start date in ISO format (YYYY-MM-DD)"
    )
    end_date: Optional[str] = Field(
        default=None,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="End date in ISO format (YYYY-MM-DD)"
    )
    days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of days to fetch (1-30)"
    )
    page: int = Field(
        default=1,
        ge=1,
        le=1000,
        description="Page number (1-indexed)"
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Results per page (max 50)"
    )


class StatsQueryParams(BaseModel):
    """Query parameters for /stats endpoint."""
    season: Optional[int] = Field(
        default=None,
        ge=2000,
        le=2100,
        description="Season year (e.g., 2025)"
    )


class RankingsQueryParams(BaseModel):
    """Query parameters for /rankings endpoint."""
    season: Optional[int] = Field(
        default=None,
        ge=2000,
        le=2100,
        description="Season year"
    )
    poll_type: str = Field(
        default="ap",
        pattern=r'^[a-z]{2,10}$',
        description="Poll type (e.g., 'ap')"
    )


class RefreshRequest(BaseModel):
    """Request model for /refresh endpoint."""
    api_key: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional authentication key"
    )
    force_regenerate: bool = Field(
        default=False,
        description="If true, delete and regenerate all predictions"
    )


class BacktestQueryParams(BaseModel):
    """Query parameters for /backtest endpoint."""
    start_date: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Start date in ISO format"
    )
    end_date: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="End date in ISO format"
    )
    model: str = Field(
        default="baseline",
        pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,29}$',
        description="Model name for backtesting"
    )


# Type alias for validated game_id path parameter
GameIdPath = Annotated[
    str,
    Path(
        ...,
        description="Game UUID",
        pattern=r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
]


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
    """
    Detailed health check.

    SECURITY: Returns only boolean configuration status, never actual key values.
    Uses secrets_validator to check configuration validity without exposing secrets.
    """
    # Check AI provider availability using validated checks
    claude_available, grok_available = check_ai_provider_available()

    # Get full secrets status (safe - only returns booleans)
    secrets_status = get_secrets_status()

    # Check Kalshi configuration
    kalshi_configured = False
    try:
        from backend.data_collection.kalshi_client import KalshiClient
        kalshi_client = KalshiClient()
        kalshi_configured = kalshi_client.is_configured
    except Exception:
        pass

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        # Validated configuration status (not just os.getenv checks)
        "supabase_configured": secrets_status.get("SUPABASE_URL", {}).get("valid", False),
        "claude_configured": claude_available,
        "grok_configured": grok_available,
        "kalshi_configured": kalshi_configured,
        # Additional detail about secrets configuration
        "secrets_valid": _secrets_validation.is_valid if '_secrets_validation' in dir() else False,
        "missing_recommended": _secrets_validation.missing_recommended if '_secrets_validation' in dir() else [],
    }


@app.post("/predict", response_model=PredictResponse)
@limiter.limit(RATE_LIMIT_AI_ENDPOINTS)
def predict(request: Request, predict_request: PredictRequest):
    """
    Get prediction for a game.

    Can provide either:
    - game_id: UUID of an existing game in the database
    - Or: home_team, away_team, spread, etc. for ad-hoc prediction

    Request body validated by PredictRequest model.

    Rate limited: 5 requests per minute per IP (AI endpoint).
    """
    if predict_request.game_id:
        # Fetch game from database
        game = get_game_by_id(predict_request.game_id)
        if not game:
            raise NotFoundException(resource="Game", identifier=predict_request.game_id)

        spread_data = get_latest_spread(predict_request.game_id)
        prediction = get_latest_prediction(predict_request.game_id)

        home_team = game.get("home_team", {}).get("name", "Unknown")
        away_team = game.get("away_team", {}).get("name", "Unknown")

        if prediction:
            return PredictResponse(
                game_id=predict_request.game_id,
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
        context = build_game_context(predict_request.game_id)
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
            game_id=predict_request.game_id,
            home_team=home_team,
            away_team=away_team,
            home_cover_prob=home_cover_prob,
            away_cover_prob=1 - home_cover_prob,
            confidence=confidence,
            recommended_bet=quick["recommended_bet"],
            edge_pct=edge_pct,
            reasoning=quick["reasoning"],
        )

    elif predict_request.home_team and predict_request.away_team:
        # Ad-hoc prediction
        context = {
            "home_team": predict_request.home_team,
            "away_team": predict_request.away_team,
            "home_rank": predict_request.home_rank,
            "away_rank": predict_request.away_rank,
            "spread": predict_request.spread,
            "is_conference_game": predict_request.is_conference_game,
        }

        quick = get_quick_recommendation(context)

        # Calculate probability based on spread
        home_cover_prob = 0.5
        confidence = "low"
        edge_pct = None

        if predict_request.spread is not None:
            spread = predict_request.spread
            # Base adjustment for home court advantage
            home_cover_prob = 0.52

            # Conference games have stronger home edge
            if predict_request.is_conference_game:
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
            home_team=predict_request.home_team,
            away_team=predict_request.away_team,
            home_cover_prob=home_cover_prob,
            away_cover_prob=1 - home_cover_prob,
            confidence=confidence,
            recommended_bet=quick["recommended_bet"],
            edge_pct=edge_pct,
            reasoning=quick["reasoning"],
        )

    # Note: This case is now handled by PredictRequest model_validator
    # If we reach here, validation already passed


@app.get("/ai-analysis")
def ai_analysis_get():
    """Debug endpoint - if you see this, the request was GET not POST."""
    return {"error": "This endpoint requires POST method", "method_received": "GET"}


@app.post("/ai-analysis", response_model=AIAnalysisResponse)
@limiter.limit(RATE_LIMIT_AI_ENDPOINTS)
def ai_analysis(request: Request, analysis_request: AIAnalysisRequest):
    """
    Generate AI analysis for a game.

    Uses Claude or Grok to analyze the matchup and provide betting recommendations.

    Rate limited: 5 requests per minute per IP (AI endpoint).
    """
    try:
        result = analyze_game(analysis_request.game_id, analysis_request.provider)

        return AIAnalysisResponse(
            game_id=analysis_request.game_id,
            provider=result["ai_provider"],
            recommended_bet=result["recommended_bet"],
            confidence_score=result["confidence_score"],
            key_factors=result["key_factors"],
            reasoning=result["reasoning"],
            created_at=result.get("created_at"),
        )

    except ValueError as e:
        # ValueError is user-input related, return sanitized message
        error_msg = str(e)[:100]  # Truncate long error messages
        raise ValidationException(
            message=error_msg,
            details={"game_id": analysis_request.game_id, "provider": analysis_request.provider}
        )
    except Exception as e:
        # Log full error server-side, return generic message to client
        logger.error(f"AI analysis failed for game {analysis_request.game_id}: {e}", exc_info=True)
        raise ExternalApiException(
            service=f"AI/{analysis_request.provider}",
            message="AI analysis failed. Please try again later."
        )


@app.get("/today")
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_today(request: Request):
    """
    Get today's games with predictions and analysis.

    Uses Eastern time for "today" since college basketball games
    are scheduled and displayed in US Eastern time.

    Rate limited: 30 requests per minute per IP.
    """
    try:
        # Use Eastern time for consistent date display
        eastern_today = get_eastern_date_today()
        games = get_today_games_view()
        return {
            "date": eastern_today.isoformat(),
            "game_count": len(games),
            "games": games,
        }
    except Exception as e:
        # SECURITY: Log error server-side, return safe response to client
        logger.error(f"Error fetching today's games: {e}", exc_info=True)
        return {
            "date": get_eastern_date_today().isoformat(),
            "game_count": 0,
            "games": [],
            "error": "Unable to fetch games. Please try again later.",
        }


@app.get("/games")
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_games(
    request: Request,
    start_date: Annotated[
        Optional[str],
        Query(
            description="Start date in ISO format (YYYY-MM-DD)",
            pattern=r'^\d{4}-\d{2}-\d{2}$',
            examples=["2025-01-21"]
        )
    ] = None,
    end_date: Annotated[
        Optional[str],
        Query(
            description="End date in ISO format (YYYY-MM-DD)",
            pattern=r'^\d{4}-\d{2}-\d{2}$',
            examples=["2025-01-28"]
        )
    ] = None,
    days: Annotated[
        int,
        Query(ge=1, le=30, description="Number of days to fetch (1-30)")
    ] = 7,
    page: Annotated[
        int,
        Query(ge=1, le=1000, description="Page number, 1-indexed")
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=50, description="Results per page (max 50)")
    ] = 20
):
    """
    Get upcoming games with pagination.

    Returns games in the same flat format as the today_games view,
    with home_team/away_team as strings (not nested objects).

    Query params:
    - start_date: ISO date string (default: today)
    - end_date: ISO date string (default: start + days)
    - days: Number of days to fetch (default: 7, max: 30)
    - page: Page number, 1-indexed (default: 1)
    - page_size: Number of games per page (default: 20, max: 50)

    Rate limited: 30 requests per minute per IP.
    """
    try:
        # Use the view which returns flat data (home_team as string, not object)
        # This matches the format expected by the frontend TodayGame type
        all_games = get_upcoming_games_view(days)

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
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_game(request: Request, game_id: GameIdPath):
    """
    Get detailed info for a specific game.

    Path params:
    - game_id: UUID of the game

    Rate limited: 30 requests per minute per IP.
    """
    game = get_game_by_id(game_id)
    if not game:
        raise NotFoundException(resource="Game", identifier=game_id)

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
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_game_analytics(request: Request, game_id: GameIdPath):
    """
    Get KenPom and Haslametrics analytics for a specific game.

    This endpoint is designed for lazy loading - fetch analytics only when
    a user expands a game card or views detailed analytics section.

    Path params:
    - game_id: UUID of the game

    Rate limited: 30 requests per minute per IP.
    """
    from .supabase_client import get_team_kenpom, get_team_haslametrics

    game = get_game_by_id(game_id)
    if not game:
        raise NotFoundException(resource="Game", identifier=game_id)

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
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_stats(
    request: Request,
    season: Annotated[
        Optional[int],
        Query(ge=2000, le=2100, description="Season year (e.g., 2025)")
    ] = None
):
    """
    Get performance statistics.

    Query params:
    - season: Year (2000-2100), defaults to current year

    Rate limited: 30 requests per minute per IP.
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
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_rankings(
    request: Request,
    season: Annotated[
        Optional[int],
        Query(ge=2000, le=2100, description="Season year")
    ] = None,
    poll_type: Annotated[
        str,
        Query(pattern=r'^[a-z]{2,10}$', description="Poll type (e.g., 'ap')")
    ] = "ap"
):
    """
    Get current AP rankings.

    Query params:
    - season: Year (2000-2100), defaults to current year
    - poll_type: Type of poll, e.g., 'ap' (default)

    Rate limited: 30 requests per minute per IP.
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
    api_key: Annotated[
        Optional[str],
        Query(max_length=100, description="Optional authentication key")
    ] = None,
    force_regenerate: Annotated[
        bool,
        Query(description="If true, delete and regenerate all predictions")
    ] = False
):
    """
    Trigger a data refresh (games, spreads, rankings).

    This endpoint should be called by a cron job or manually.

    Query params:
    - api_key: Optional authentication key (max 100 chars)
    - force_regenerate: If true, delete and regenerate all predictions
    """
    # Simple API key check (only if REFRESH_API_KEY is set in environment)
    expected_key = os.getenv("REFRESH_API_KEY")
    if expected_key and api_key and api_key != expected_key:
        raise ApiException(
            status_code=401,
            code="UNAUTHORIZED",
            message="Invalid API key"
        )
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


@app.post("/refresh-prediction-markets")
def refresh_prediction_markets_endpoint():
    """
    Quick endpoint to refresh only prediction market data (Polymarket + Kalshi).
    Much faster than full /refresh - useful for testing.
    """
    try:
        import asyncio
        from ..data_collection.prediction_market_scraper import refresh_prediction_markets

        results = asyncio.run(refresh_prediction_markets())

        return {
            "status": results.get("status", "success"),
            "timestamp": results.get("timestamp"),
            "polymarket": results.get("polymarket", {}),
            "kalshi": results.get("kalshi", {}),
            "arbitrage": results.get("arbitrage", {}),
        }
    except ImportError as e:
        logger.error(f"Prediction market import error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": "Service configuration error",
        }
    except Exception as e:
        logger.error(f"Prediction market refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Prediction market refresh failed. Please try again later.")


@app.get("/prediction-markets")
def get_prediction_markets():
    """
    Get stored prediction market data with team names.
    """
    try:
        from .supabase_client import get_supabase
        supabase = get_supabase()

        # Get prediction markets with team names
        result = supabase.table("prediction_markets").select(
            "source, market_id, title, market_type, status, team_id, game_id"
        ).eq("status", "open").limit(50).execute()

        markets = result.data or []

        # Get team names for matched markets
        team_ids = [m["team_id"] for m in markets if m.get("team_id")]
        if team_ids:
            teams_result = supabase.table("teams").select("id, name").in_("id", team_ids).execute()
            team_map = {t["id"]: t["name"] for t in (teams_result.data or [])}
            for m in markets:
                if m.get("team_id"):
                    m["team_name"] = team_map.get(m["team_id"])

        return {
            "count": len(markets),
            "markets": markets
        }
    except Exception as e:
        logger.error(f"Failed to get prediction markets: {e}")
        return {"error": str(e)}


@app.get("/test-kalshi")
def test_kalshi_endpoint():
    """
    Diagnostic endpoint to test Kalshi API connection.
    Returns authentication status and market availability summary.
    """
    try:
        import asyncio
        from ..data_collection.kalshi_client import KalshiClient, KALSHI_BASE_URL

        client = KalshiClient()

        results = {
            "is_configured": client.is_configured,
            "has_api_key": bool(client.api_key),
            "has_private_key": bool(client.private_key_content or client.private_key_path),
        }

        if not client.is_configured:
            results["error"] = "Kalshi not configured - need KALSHI_API_KEY and KALSHI_PRIVATE_KEY"
            return results

        # Test the private key loading
        try:
            pk = client.private_key
            results["private_key_loaded"] = pk is not None
        except Exception as e:
            results["private_key_error"] = str(e)
            return results

        async def test_fetch():
            # Quick scan of first 500 markets
            standalone_cbb = 0
            parlay_cbb = 0
            total = 0
            cursor = None

            for _ in range(5):  # 5 pages
                path = "/markets"
                params = {"limit": 100, "status": "open"}
                if cursor:
                    params["cursor"] = cursor
                headers = client._get_headers("GET", path)

                response = await client.client.get(path, headers=headers, params=params)
                if response.status_code != 200:
                    return {"api_status": response.status_code, "error": "API request failed"}

                data = response.json()
                batch = data.get("markets", [])
                total += len(batch)

                for m in batch:
                    ticker = m.get("ticker", "")
                    market_str = str(m)

                    if ticker.upper().startswith("KXNCAAMB"):
                        standalone_cbb += 1
                    elif "NCAAMB" in market_str.upper():
                        parlay_cbb += 1

                cursor = data.get("cursor")
                if not cursor or not batch:
                    break

            return {
                "api_status": 200,
                "markets_scanned": total,
                "standalone_cbb_markets": standalone_cbb,
                "parlay_cbb_references": parlay_cbb,
                "note": "Kalshi currently has NCAAMB only in multi-game parlays, not standalone markets"
            }

        fetch_result = asyncio.run(test_fetch())
        results.update(fetch_result)
        asyncio.run(client.close())

        return results

    except Exception as e:
        logger.error(f"Kalshi test failed: {e}", exc_info=True)
        return {"error": str(e)}


@app.post("/refresh-espn-times")
def refresh_espn_times_endpoint(
    days: Annotated[
        int,
        Query(ge=1, le=14, description="Number of days ahead to fetch (max 14)")
    ] = 7
):
    """
    Update game tip times from ESPN's public API.

    This fetches real scheduled game times and updates our games table.
    Fast operation - no authentication required, can be run frequently.

    Query params:
    - days: Number of days ahead to fetch (default: 7, max: 14)
    """
    try:
        from ..data_collection.espn_scraper import refresh_espn_tip_times

        results = refresh_espn_tip_times(days=days)

        return {
            "status": "success",
            "results": results,
        }
    except ImportError as e:
        # SECURITY: Log detailed error server-side
        logger.error(f"ESPN scraper import error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": "Service configuration error",
        }
    except Exception as e:
        # SECURITY: Log error server-side, return generic message to client
        logger.error(f"ESPN tip times refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="ESPN tip times refresh failed. Please try again later.")


@app.get("/backtest")
def backtest(
    start_date: Annotated[
        str,
        Query(
            ...,
            pattern=r'^\d{4}-\d{2}-\d{2}$',
            description="Start date in ISO format (YYYY-MM-DD)"
        )
    ],
    end_date: Annotated[
        str,
        Query(
            ...,
            pattern=r'^\d{4}-\d{2}-\d{2}$',
            description="End date in ISO format (YYYY-MM-DD)"
        )
    ],
    model: Annotated[
        str,
        Query(
            pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,29}$',
            description="Model name (letters, numbers, underscore, hyphen, max 30 chars)"
        )
    ] = "baseline"
):
    """
    Run backtest on historical data.

    Query params:
    - start_date: Start date in ISO format (required)
    - end_date: End date in ISO format (required)
    - model: Model name for backtesting (default: baseline)
    """
    # Validate date range
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if end < start:
            raise ValidationException(
                message="end_date must be after start_date",
                details={"start_date": start_date, "end_date": end_date}
            )
    except ValueError as e:
        raise ValidationException(
            message="Invalid date format",
            details={"error": str(e)}
        )

    # TODO: Implement backtesting
    return {
        "start_date": start_date,
        "end_date": end_date,
        "model": model,
        "message": "Backtesting not yet implemented",
    }


@app.get("/debug/ai-analysis/{game_id}")
@limiter.limit(RATE_LIMIT_AI_ENDPOINTS)
def debug_ai_analysis(request: Request, game_id: GameIdPath, provider: Literal["claude", "grok"] = "claude"):
    """
    Debug endpoint to diagnose AI analysis issues.
    Returns detailed error information instead of generic messages.

    WARNING: This endpoint exposes internal errors - remove in production!

    Rate limited: 5 requests per minute per IP (AI endpoint).
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

    # Step 3: Check API keys (using secrets validator - never expose actual keys)
    claude_available, grok_available = check_ai_provider_available()
    results["steps"]["3_api_keys"] = {
        "anthropic_configured": claude_available,
        "grok_configured": grok_available,
    }

    if provider == "claude" and not claude_available:
        results["errors"].append("Claude API key not configured or invalid")
    if provider == "grok" and not grok_available:
        results["errors"].append("Grok API key not configured or invalid")

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
    # Note: The debug endpoint just verifies the flow - actual insert uses analyze_game()
    # which passes the full analysis_result dict with correct column names
    try:
        from .supabase_client import insert_ai_analysis

        # The analysis_result from AI already has correct column names matching the table:
        # ai_provider, model_used, analysis_type, prompt_hash, response, recommended_bet,
        # confidence_score, key_factors, reasoning, tokens_used
        insert_data = {
            "game_id": game_id,
            "ai_provider": analysis_result.get("ai_provider", provider),
            "model_used": analysis_result.get("model_used"),
            "analysis_type": analysis_result.get("analysis_type", "matchup"),
            "prompt_hash": analysis_result.get("prompt_hash"),
            "response": analysis_result.get("response", ""),  # Full AI response text
            "recommended_bet": analysis_result.get("recommended_bet"),
            "confidence_score": analysis_result.get("confidence_score"),
            "key_factors": analysis_result.get("key_factors", []),
            "reasoning": analysis_result.get("reasoning", ""),
            "tokens_used": analysis_result.get("tokens_used"),
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
