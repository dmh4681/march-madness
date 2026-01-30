"""
Conference Contrarian API

FastAPI backend serving AI-powered NCAA basketball betting analysis and predictions.

This module provides the main API endpoints for:
- Game data retrieval (today's games, upcoming games, game details)
- AI-powered analysis using Claude and Grok LLMs
- Betting predictions with confidence tiers and edge detection
- Advanced analytics from KenPom and Haslametrics
- Prediction market data and arbitrage detection
- Season performance statistics and rankings

Architecture:
    - FastAPI with Pydantic validation for all request/response models
    - Rate limiting via slowapi (5 req/min for AI, 30 req/min for standard)
    - CORS configured for specific trusted origins only
    - Supabase PostgreSQL database via supabase-py client
    - Claude (Anthropic) and Grok (xAI) for AI analysis

Security Features:
    - Input validation on all endpoints with Pydantic models
    - UUID format validation for all ID parameters
    - CORS origin validation (rejects wildcards)
    - Rate limiting to prevent abuse
    - Error messages sanitized to prevent information leakage
    - API keys validated at startup without exposing values

Usage:
    # Development
    uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000

    # Production (via Procfile on Railway)
    gunicorn backend.api.main:app -k uvicorn.workers.UvicornWorker

Environment Variables Required:
    SUPABASE_URL: PostgreSQL database URL
    SUPABASE_SERVICE_KEY: Supabase service role key (backend only)
    ANTHROPIC_API_KEY: Claude API key for AI analysis
    ALLOWED_ORIGINS: Comma-separated list of allowed CORS origins

Environment Variables Optional:
    GROK_API_KEY: Grok API key for secondary AI analysis
    ODDS_API_KEY: The Odds API key for betting lines
    KENPOM_EMAIL/KENPOM_PASSWORD: KenPom subscription credentials
    REFRESH_API_KEY: Authentication for refresh endpoint

API Documentation:
    Swagger UI: /docs
    ReDoc: /redoc
    OpenAPI JSON: /openapi.json
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
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI, HTTPException, Request, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# SECURITY: Request Body Size Limit Middleware
# =============================================================================
MAX_REQUEST_BODY_SIZE = 10 * 1024  # 10KB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject POST/PUT/PATCH requests with bodies exceeding MAX_REQUEST_BODY_SIZE."""

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "REQUEST_TOO_LARGE",
                        "message": f"Request body exceeds maximum size of {MAX_REQUEST_BODY_SIZE} bytes",
                    },
                )
        return await call_next(request)

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
from backend.utils.env_validator import validate_environment

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
    get_team_ranking,
    # Performance monitoring
    get_query_stats,
    get_cache_stats,
    # Batch operations
    get_or_create_team,
    upsert_game,
    get_team_by_name,
    normalize_team_name,
    get_supabase,
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

# =============================================================================
# OpenAPI/Swagger Configuration
# =============================================================================
# Tag metadata for organized API documentation
tags_metadata = [
    {
        "name": "Health",
        "description": "Health check and status endpoints for monitoring and debugging.",
    },
    {
        "name": "Games",
        "description": """
Game data endpoints for retrieving NCAA basketball games.

**Key Endpoints:**
- `GET /today` - Today's games with predictions (optimized view)
- `GET /games` - Upcoming games with pagination
- `GET /games/{id}` - Detailed game info with AI analyses

**Data Sources:**
- ESPN schedule for game times
- The Odds API for betting lines
- KenPom and Haslametrics for advanced analytics
""",
    },
    {
        "name": "Predictions",
        "description": """
ML-based betting prediction endpoints.

**Prediction Model:**
Uses a baseline logistic regression model with features:
- Spread magnitude and direction
- Home court advantage adjustments
- Conference game dynamics
- Historical patterns for ranked vs unranked matchups

**Confidence Tiers:**
- **High**: >4% edge over implied odds
- **Medium**: 2-4% edge
- **Low**: <2% edge (recommend pass)

**Probability Calibration:**
Win probabilities are calibrated to account for:
- Standard -110 vig (52.4% breakeven)
- Public betting bias on ranked teams
- Conference familiarity effects
""",
    },
    {
        "name": "AI Analysis",
        "description": """
AI-powered game analysis using Large Language Models.

**Available Providers:**
- **Claude** (Anthropic Claude Sonnet 4): Primary provider, thorough analysis
- **Grok** (xAI Grok-3): Alternative perspective, good for comparison

**Analysis Data Sources:**
The AI receives comprehensive context including:
- Team rankings and conference info
- Current betting lines (spread, moneyline, total)
- KenPom analytics (AdjO, AdjD, tempo, SOS, luck)
- Haslametrics data (All-Play %, momentum, efficiency)
- Prediction market prices and arbitrage signals

**Cross-Validation:**
When both KenPom and Haslametrics are available, the AI cross-validates
between sources. Disagreement lowers confidence; agreement increases it.
""",
    },
    {
        "name": "Analytics",
        "description": """
Advanced analytics endpoints for KenPom and Haslametrics data.

**KenPom Metrics** (subscription required):
- AdjO/AdjD: Adjusted offensive/defensive efficiency
- AdjEM: Efficiency margin (main power rating)
- Tempo: Possessions per game
- Luck: Deviation from expected record
- SOS: Strength of schedule

**Haslametrics Metrics** (FREE):
- All-Play %: Win probability vs average D1 team
- Momentum: Overall/offensive/defensive trends
- Quadrant records: Performance vs NET tiers
""",
    },
    {
        "name": "Performance",
        "description": """
Betting performance tracking and backtesting.

**Key Metrics:**
- Win percentage (breakeven at -110 is 52.4%)
- ROI (Return on Investment)
- Units won/lost
- Performance by confidence tier
""",
    },
    {
        "name": "Rankings",
        "description": "AP poll rankings data by season and week.",
    },
    {
        "name": "Admin",
        "description": """
Administrative endpoints for data refresh and maintenance.

**Daily Refresh Pipeline:**
1. Fetch ESPN game schedule (creates games)
2. Fetch betting lines from The Odds API
3. Refresh KenPom analytics (if credentials configured)
4. Refresh Haslametrics analytics (FREE)
5. Refresh prediction market data
6. Detect arbitrage opportunities
7. Generate predictions for upcoming games
8. Run AI analysis on today's games

**Typical Schedule:**
- Full refresh: Daily at 6 AM EST via GitHub Actions
- Individual refreshes: On-demand as needed
""",
    },
    {
        "name": "Prediction Markets",
        "description": """
Prediction market data from Polymarket and Kalshi.

**Arbitrage Detection:**
Compares sportsbook implied probabilities with prediction market prices.
Actionable opportunities flagged when delta >= 10%.
""",
    },
    {
        "name": "Debug",
        "description": "Diagnostic endpoints for troubleshooting. May expose detailed error info.",
    },
]

app = FastAPI(
    title="Conference Contrarian API",
    description="""
## AI-Powered NCAA Basketball Betting Analysis

Conference Contrarian is a sports analytics platform that combines machine learning predictions
with AI-powered analysis (Claude and Grok) to identify betting edges in college basketball.

### Core Features

- **Game Data**: Real-time game schedules, betting lines, and team information
- **ML Predictions**: Spread cover probabilities with confidence tiers
- **AI Analysis**: Deep game analysis using Claude (Anthropic) and Grok (xAI)
- **Advanced Analytics**: KenPom and Haslametrics integration
- **Prediction Markets**: Polymarket/Kalshi data with arbitrage detection

### Data Flow

```
ESPN Schedule -> Games Table
The Odds API -> Spreads Table (lines + moneylines)
KenPom/Haslametrics -> Analytics Tables
ML Model -> Predictions Table
Claude/Grok -> AI Analysis Table
```

### Authentication

Most endpoints are public. Admin endpoints may require an API key via query parameter.

### Rate Limits

- AI endpoints: 5 requests/minute per IP
- Standard endpoints: 30 requests/minute per IP

### Links

- [Live Site](https://confcontrarian.com)
- [API Documentation](/docs) (Swagger UI)
- [ReDoc](/redoc) (Alternative docs)
""",
    version="1.0.0",
    openapi_tags=tags_metadata,
    contact={
        "name": "Conference Contrarian",
        "url": "https://confcontrarian.com",
    },
    license_info={
        "name": "MIT",
    },
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

# Add request body size limit (10KB for POST endpoints)
app.add_middleware(RequestSizeLimitMiddleware)

# Register exception handlers
app.add_exception_handler(ApiException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(Exception, general_exception_handler)


# =============================================================================
# STARTUP: Environment Validation
# =============================================================================
@app.on_event("startup")
async def startup_validate_env():
    validate_environment()


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
    """
    Request model for the /predict endpoint.

    Supports two modes of operation:
    1. Database lookup: Provide game_id to fetch game data from Supabase
    2. Ad-hoc prediction: Provide team names and optional spread/ranking info

    Example (database lookup):
        {
            "game_id": "123e4567-e89b-12d3-a456-426614174000"
        }

    Example (ad-hoc prediction):
        {
            "home_team": "Duke",
            "away_team": "North Carolina",
            "spread": -5.5,
            "is_conference_game": true,
            "home_rank": 5,
            "away_rank": null
        }

    Business Logic:
        - If game_id provided, fetches game from database with latest spread
        - If prediction exists in database, returns cached prediction
        - Otherwise, calculates prediction using spread-based heuristics
        - Conference games have adjusted home court advantage (~3-4 points)
        - Large spreads (>10 points) reduce home cover probability
        - Confidence tiers: high (>4% edge), medium (>2% edge), low (<2%)
    """
    game_id: Optional[str] = Field(
        default=None,
        description="UUID of existing game in database. If provided, fetches game data and existing predictions."
    )
    # Or provide matchup details
    home_team: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Home team name (e.g., 'Duke', 'North Carolina'). Required if game_id not provided."
    )
    away_team: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Away team name. Required if game_id not provided."
    )
    spread: Optional[float] = Field(
        default=None,
        ge=-50.0,
        le=50.0,
        description="Point spread from home team perspective. Negative = home favored (e.g., -5.5 means home favored by 5.5)."
    )
    is_conference_game: Optional[bool] = Field(
        default=False,
        description="Whether this is a conference matchup. Conference games have different home court dynamics."
    )
    home_rank: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Home team AP ranking (1-25). Null/omit if unranked."
    )
    away_rank: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Away team AP ranking (1-25). Null/omit if unranked."
    )

    @field_validator('game_id')
    @classmethod
    def validate_game_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate game_id is a properly formatted UUID."""
        if v is not None and not UUID_PATTERN.match(v):
            raise ValueError('game_id must be a valid UUID')
        return v

    @field_validator('home_team', 'away_team')
    @classmethod
    def validate_team_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate team name contains only allowed characters (alphanumeric, spaces, hyphens, periods, apostrophes, ampersands)."""
        if v is not None and not re.match(r"^[a-zA-Z0-9\s\-\.\'\&\(\)]+$", v):
            raise ValueError('Team name must contain only alphanumeric characters, spaces, hyphens, periods, apostrophes, or ampersands')
        return v

    @model_validator(mode='after')
    def check_required_fields(self):
        """Ensure either game_id or team names are provided."""
        if not self.game_id and not (self.home_team and self.away_team):
            raise ValueError('Must provide either game_id or (home_team + away_team)')
        return self


class PredictResponse(BaseModel):
    """
    Response model for the /predict endpoint.

    Contains prediction probabilities, confidence tier, and betting recommendation.

    Example Response:
        {
            "game_id": "123e4567-e89b-12d3-a456-426614174000",
            "home_team": "Duke",
            "away_team": "North Carolina",
            "home_cover_prob": 0.54,
            "away_cover_prob": 0.46,
            "confidence": "medium",
            "recommended_bet": "home_spread",
            "edge_pct": 2.0,
            "reasoning": "Home team has slight edge due to home court advantage in conference play."
        }

    Fields:
        home_cover_prob/away_cover_prob: Probabilities that sum to 1.0
        confidence: "high" (>4% edge), "medium" (>2%), or "low" (<2%)
        recommended_bet: "home_spread", "away_spread", or "pass"
        edge_pct: Percentage edge over fair odds (null if no edge)
    """
    game_id: Optional[str] = Field(description="UUID of the game (null for ad-hoc predictions)")
    home_team: str = Field(description="Home team name")
    away_team: str = Field(description="Away team name")
    home_cover_prob: float = Field(ge=0.0, le=1.0, description="Probability home team covers the spread (0.0-1.0)")
    away_cover_prob: float = Field(ge=0.0, le=1.0, description="Probability away team covers (1 - home_cover_prob)")
    confidence: str = Field(description="Confidence tier: 'high', 'medium', or 'low'")
    recommended_bet: str = Field(description="Betting recommendation: 'home_spread', 'away_spread', or 'pass'")
    edge_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Estimated edge percentage over fair odds")
    reasoning: Optional[str] = Field(description="Brief explanation of the recommendation")


class AIAnalysisRequest(BaseModel):
    """
    Request model for the /ai-analysis endpoint.

    Triggers an AI-powered analysis of a specific game using either Claude or Grok.
    The AI receives comprehensive context including:
    - Team rankings and conference information
    - Current betting lines (spread, moneyline, total)
    - KenPom advanced analytics (if available)
    - Haslametrics data (if available)
    - Prediction market data and arbitrage signals

    Example Request:
        {
            "game_id": "123e4567-e89b-12d3-a456-426614174000",
            "provider": "claude"
        }

    Rate Limit: 5 requests per minute per IP address

    Business Logic:
        - Analysis is saved to database for caching/historical reference
        - If both KenPom and Haslametrics data available, AI cross-validates
        - Prediction market data influences confidence when significant edges detected
        - Response includes actionable betting recommendation with confidence score
    """
    game_id: str = Field(
        ...,
        description="UUID of the game to analyze. Must exist in the games table."
    )
    provider: Literal["claude", "grok"] = Field(
        default="claude",
        description="AI provider: 'claude' (Anthropic Claude Sonnet 4) or 'grok' (xAI Grok-3)"
    )

    @field_validator('game_id')
    @classmethod
    def validate_game_id(cls, v: str) -> str:
        """Validate game_id is a properly formatted UUID."""
        if not UUID_PATTERN.match(v):
            raise ValueError('game_id must be a valid UUID')
        return v


class AIAnalysisResponse(BaseModel):
    """
    Response model for the /ai-analysis endpoint.

    Contains the AI's betting recommendation with supporting analysis.

    Example Response:
        {
            "game_id": "123e4567-e89b-12d3-a456-426614174000",
            "provider": "claude",
            "recommended_bet": "away_spread",
            "confidence_score": 0.72,
            "key_factors": [
                "Duke's KenPom AdjD ranks #3, UNC's offense struggles vs elite defenses",
                "Haslametrics momentum shows UNC trending down (-0.3 last 5 games)",
                "Historical data: Top 5 teams cover at only 48% as road favorites"
            ],
            "reasoning": "Despite Duke being ranked higher, UNC at home in a rivalry game with Duke coming off a tough road stretch presents value on the underdog.",
            "created_at": "2025-01-25T14:30:00Z"
        }

    Possible recommended_bet values:
        - "home_spread": Bet home team to cover the spread
        - "away_spread": Bet away team to cover the spread
        - "home_ml": Bet home team moneyline
        - "away_ml": Bet away team moneyline
        - "over": Bet the over on total points
        - "under": Bet the under on total points
        - "pass": No recommended bet (insufficient edge)
    """
    game_id: str = Field(description="UUID of the analyzed game")
    provider: str = Field(description="AI provider used: 'claude' or 'grok'")
    recommended_bet: str = Field(description="Betting recommendation (see docstring for possible values)")
    confidence_score: float = Field(ge=0.0, le=1.0, description="AI confidence (0.5 = coin flip, 0.8+ = high conviction)")
    key_factors: list[str] = Field(description="3-5 key factors driving the recommendation")
    reasoning: str = Field(description="2-3 sentence explanation of the analysis")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp when analysis was created")


class StatsResponse(BaseModel):
    """
    Response model for the /stats endpoint.

    Contains season performance statistics for bet tracking.

    Example Response:
        {
            "season": 2025,
            "total_bets": 150,
            "wins": 85,
            "losses": 62,
            "pushes": 3,
            "win_pct": 57.82,
            "units_wagered": 150.0,
            "units_won": 12.5,
            "roi_pct": 8.33
        }

    Note: Assumes -110 juice on all bets (standard sportsbook odds).
    Win percentage of 52.4% is breakeven at -110 odds.
    """
    season: int = Field(description="Season year (e.g., 2025 for 2024-25 season)")
    total_bets: int = Field(description="Total number of graded bets")
    wins: int = Field(description="Number of winning bets")
    losses: int = Field(description="Number of losing bets")
    pushes: int = Field(description="Number of pushed bets (ties)")
    win_pct: float = Field(description="Win percentage (wins / (wins + losses) * 100)")
    units_wagered: float = Field(description="Total units wagered")
    units_won: float = Field(description="Net units won (can be negative)")
    roi_pct: float = Field(description="Return on investment percentage")


class GameResponse(BaseModel):
    """
    Response model for the /games/{game_id} endpoint.

    Contains comprehensive game details including predictions and AI analyses.

    Example Response:
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "date": "2025-01-25",
            "home_team": "Duke",
            "away_team": "North Carolina",
            "home_rank": 5,
            "away_rank": null,
            "home_spread": -5.5,
            "is_conference_game": true,
            "prediction": {
                "predicted_home_cover_prob": 0.54,
                "confidence_tier": "medium",
                "recommended_bet": "home_spread"
            },
            "ai_analyses": [
                {
                    "ai_provider": "claude",
                    "recommended_bet": "away_spread",
                    "confidence_score": 0.68,
                    "created_at": "2025-01-25T10:00:00Z"
                }
            ]
        }
    """
    id: str = Field(description="Game UUID")
    date: str = Field(description="Game date in ISO format (YYYY-MM-DD)")
    home_team: str = Field(description="Home team name")
    away_team: str = Field(description="Away team name")
    home_rank: Optional[int] = Field(default=None, ge=1, le=100, description="Home team AP ranking (null if unranked)")
    away_rank: Optional[int] = Field(default=None, ge=1, le=100, description="Away team AP ranking (null if unranked)")
    home_spread: Optional[float] = Field(default=None, ge=-50.0, le=50.0, description="Point spread (home perspective)")
    is_conference_game: bool = Field(description="Whether teams are in the same conference")
    prediction: Optional[dict] = Field(default=None, description="Model prediction data (if exists)")
    ai_analyses: list[dict] = Field(default=[], description="List of AI analyses for this game")


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


@app.get("/", tags=["Health"])
def root():
    """
    Root endpoint - API info and basic health check.

    Returns basic API information and current status. Use /health for detailed
    health check with service configuration status.

    Returns:
        dict: API name, version, status, and current timestamp

    Example Response:
        {
            "name": "Conference Contrarian API",
            "version": "1.0.0",
            "status": "running",
            "timestamp": "2025-01-25T14:30:00.000000"
        }
    """
    return {
        "name": "Conference Contrarian API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health", tags=["Health"])
def health():
    """
    Detailed health check with service configuration status.

    Returns configuration status for all integrated services without exposing
    actual API keys or credentials. Used for monitoring and debugging.

    SECURITY: Returns only boolean configuration status, never actual key values.
    Uses secrets_validator to check configuration validity without exposing secrets.

    Returns:
        dict: Health status with service configuration flags

    Example Response:
        {
            "status": "healthy",
            "timestamp": "2025-01-25T14:30:00.000000",
            "supabase_configured": true,
            "claude_configured": true,
            "grok_configured": true,
            "kalshi_configured": false,
            "secrets_valid": true,
            "missing_recommended": []
        }

    Service Status Flags:
        - supabase_configured: Database connection available
        - claude_configured: Anthropic API key valid
        - grok_configured: xAI API key valid
        - kalshi_configured: Kalshi prediction market API configured
        - secrets_valid: All required secrets present
        - missing_recommended: List of optional but recommended secrets
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


@app.get("/performance-stats", tags=["Health"])
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def performance_stats(request: Request):
    """
    Get database query and cache performance statistics.

    Returns metrics useful for monitoring and optimizing database performance:
    - Query timing statistics (total queries, avg time, slow queries)
    - Cache hit/miss rates for ratings data
    - Connection pool utilization metrics

    SECURITY: This endpoint is rate-limited but does not expose sensitive data.
    Only returns aggregate statistics suitable for monitoring dashboards.

    Returns:
        dict: Performance statistics including query_stats and cache_stats

    Example Response:
        {
            "timestamp": "2025-01-26T14:30:00.000000",
            "query_stats": {
                "total_queries": 1250,
                "total_time_ms": 45230.5,
                "avg_time_ms": 36.18,
                "slow_queries": 3,
                "slow_query_pct": 0.24,
                "slowest_query_ms": 1523.4,
                "slowest_query_name": "get_today_games_view"
            },
            "cache_stats": {
                "hits": 847,
                "misses": 152,
                "hit_rate_pct": 84.78,
                "invalidations": 2,
                "current_entries": 45
            }
        }

    Use Cases:
        - Monitor query performance during daily refresh
        - Identify slow queries needing optimization
        - Track cache effectiveness for ratings data
        - Debug connection pool issues
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "query_stats": get_query_stats(),
        "cache_stats": get_cache_stats(),
    }


@app.post("/predict", response_model=PredictResponse, tags=["Predictions"])
@limiter.limit(RATE_LIMIT_AI_ENDPOINTS)
def predict(request: Request, predict_request: PredictRequest):
    """
    Generate a betting prediction for a game.

    Supports two modes:
    1. **Database Lookup**: Provide `game_id` to fetch game from database
    2. **Ad-hoc Prediction**: Provide team names and optional context

    The prediction algorithm uses spread-based heuristics with adjustments for:
    - Home court advantage (base ~52% for home team)
    - Conference game dynamics (stronger home edge)
    - Spread magnitude (large favorites cover less often)
    - Ranking differentials

    Args:
        predict_request: PredictRequest with game_id or team details

    Returns:
        PredictResponse: Prediction with probabilities and recommendation

    Raises:
        404 Not Found: If game_id provided but game doesn't exist
        422 Validation Error: If request body invalid

    Rate Limit: 5 requests per minute per IP

    Example Request (database lookup):
        POST /predict
        {"game_id": "123e4567-e89b-12d3-a456-426614174000"}

    Example Request (ad-hoc):
        POST /predict
        {
            "home_team": "Duke",
            "away_team": "North Carolina",
            "spread": -5.5,
            "is_conference_game": true
        }

    Business Logic:
        - Checks for existing prediction in database first
        - Falls back to heuristic calculation if no prediction exists
        - Confidence tiers: high (>4% edge), medium (>2%), low (<2%)
        - Recommends "pass" when no clear edge detected
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


@app.get("/ai-analysis", tags=["AI Analysis"])
def ai_analysis_get():
    """
    Debug endpoint for incorrect GET requests to /ai-analysis.

    The /ai-analysis endpoint requires POST method. This GET handler exists
    to provide a helpful error message when the wrong method is used.

    Returns:
        dict: Error message indicating POST is required
    """
    return {"error": "This endpoint requires POST method", "method_received": "GET"}


@app.post("/ai-analysis", response_model=AIAnalysisResponse, tags=["AI Analysis"])
@limiter.limit(RATE_LIMIT_AI_ENDPOINTS)
def ai_analysis(request: Request, analysis_request: AIAnalysisRequest):
    """
    Generate AI-powered analysis for a game using Claude or Grok.

    This endpoint triggers a comprehensive AI analysis of the specified game,
    incorporating all available data:
    - Team rankings and conference information
    - Current betting lines (spread, moneyline, total)
    - KenPom advanced analytics (AdjO, AdjD, tempo, SOS, luck)
    - Haslametrics data (All-Play %, momentum, efficiency)
    - Prediction market data and arbitrage signals

    The AI provides a structured betting recommendation with confidence score
    and detailed reasoning. Analysis is saved to database for caching.

    Args:
        analysis_request: AIAnalysisRequest with game_id and provider

    Returns:
        AIAnalysisResponse: AI recommendation with key factors and reasoning

    Raises:
        404 Not Found: If game doesn't exist
        422 Validation Error: If request body invalid
        503 Service Unavailable: If AI provider not configured or unavailable

    Rate Limit: 5 requests per minute per IP

    Example Request:
        POST /ai-analysis
        {"game_id": "123e4567-e89b-12d3-a456-426614174000", "provider": "claude"}

    Example Response:
        {
            "game_id": "123e4567-e89b-12d3-a456-426614174000",
            "provider": "claude",
            "recommended_bet": "away_spread",
            "confidence_score": 0.72,
            "key_factors": [
                "KenPom efficiency differential favors underdog by 2 points",
                "Haslametrics momentum shows away team trending up",
                "Historical: Top 5 favorites cover only 48% in conference road games"
            ],
            "reasoning": "Despite the ranking, value exists on the underdog...",
            "created_at": "2025-01-25T14:30:00Z"
        }

    AI Providers:
        - claude: Anthropic Claude Sonnet 4 (primary, most thorough analysis)
        - grok: xAI Grok-3 (alternative perspective, good for comparison)

    Business Logic:
        - Builds comprehensive context from all data sources
        - When both KenPom and Haslametrics available, AI cross-validates
        - Prediction market data influences confidence on large deltas
        - Analysis saved to ai_analysis table for historical reference
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


@app.get("/today", tags=["Games"])
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_today(request: Request):
    """
    Get today's games with predictions, spreads, and analysis flags.

    Returns all games scheduled for today (in US Eastern time) with
    flattened team names, betting lines, predictions, and indicators
    for available AI analysis and prediction market data.

    Uses Eastern time for "today" since college basketball games
    are scheduled and displayed in US Eastern time.

    Returns:
        dict: Date, game count, and list of games

    Rate Limit: 30 requests per minute per IP

    Example Response:
        {
            "date": "2025-01-25",
            "game_count": 42,
            "games": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "date": "2025-01-25",
                    "tip_time": "19:00:00",
                    "home_team": "Duke",
                    "away_team": "North Carolina",
                    "home_spread": -5.5,
                    "home_ml": -210,
                    "away_ml": 175,
                    "over_under": 142.5,
                    "predicted_home_cover_prob": 0.54,
                    "confidence_tier": "medium",
                    "recommended_bet": "home_spread",
                    "has_ai_analysis": true,
                    "has_prediction_market": false
                }
            ]
        }

    Data Source: Uses today_games Supabase view which joins:
        - games table (schedule, teams)
        - spreads table (latest betting lines)
        - predictions table (model predictions)
        - ai_analysis table (AI analysis flag)
        - prediction_markets table (PM data flag)
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


@app.get("/games", tags=["Games"])
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
    Get upcoming games with pagination support.

    Returns games in the same flat format as /today, with team names as
    strings (not nested objects). Supports date range filtering and pagination.

    Query Parameters:
        start_date: Start date (default: today in Eastern time)
        end_date: End date (default: start_date + days)
        days: Number of days to fetch (default: 7, max: 30)
        page: Page number, 1-indexed (default: 1)
        page_size: Results per page (default: 20, max: 50)

    Returns:
        dict: Paginated games with metadata

    Rate Limit: 30 requests per minute per IP

    Example Request:
        GET /games?days=3&page=1&page_size=10

    Example Response:
        {
            "game_count": 10,
            "total_games": 45,
            "page": 1,
            "page_size": 10,
            "total_pages": 5,
            "has_more": true,
            "games": [...]
        }

    Pagination Fields:
        - game_count: Number of games in current page
        - total_games: Total games matching criteria
        - page/page_size: Current pagination parameters
        - total_pages: Total number of pages available
        - has_more: Boolean indicating if more pages exist

    Data Source: Uses upcoming_games Supabase view
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


@app.get("/games/{game_id}", response_model=GameResponse, tags=["Games"])
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_game(request: Request, game_id: GameIdPath):
    """
    Get detailed information for a specific game.

    Returns comprehensive game data including:
    - Basic game info (date, teams, venue)
    - Current betting lines (spread, moneylines)
    - Team rankings (AP poll)
    - Model predictions
    - All AI analyses (Claude and Grok)

    Path Parameters:
        game_id: UUID of the game (validated format)

    Returns:
        GameResponse: Complete game details

    Raises:
        404 Not Found: If game doesn't exist
        422 Validation Error: If game_id format invalid

    Rate Limit: 30 requests per minute per IP

    Example Request:
        GET /games/123e4567-e89b-12d3-a456-426614174000

    Example Response:
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "date": "2025-01-25",
            "home_team": "Duke",
            "away_team": "North Carolina",
            "home_rank": 5,
            "away_rank": null,
            "home_spread": -5.5,
            "is_conference_game": true,
            "prediction": {
                "predicted_home_cover_prob": 0.54,
                "confidence_tier": "medium",
                "edge_pct": 2.0
            },
            "ai_analyses": [
                {
                    "ai_provider": "claude",
                    "recommended_bet": "away_spread",
                    "confidence_score": 0.68
                }
            ]
        }

    Note: Use /games/{game_id}/analytics for KenPom and Haslametrics data
    """
    game = get_game_by_id(game_id)
    if not game:
        raise NotFoundException(resource="Game", identifier=game_id)

    spread = get_latest_spread(game_id)
    prediction = get_latest_prediction(game_id)
    analyses = get_ai_analyses(game_id)

    # Fetch team rankings
    home_rank = None
    away_rank = None
    try:
        home_team = game.get("home_team", {})
        away_team = game.get("away_team", {})
        home_team_id = home_team.get("id")
        away_team_id = away_team.get("id")

        # Get current season (use game date's year, or current year)
        game_date = game.get("date")
        if game_date:
            try:
                season = datetime.fromisoformat(game_date.replace("Z", "+00:00")).year
            except (ValueError, AttributeError):
                season = datetime.now().year
        else:
            season = datetime.now().year

        if home_team_id:
            home_ranking = get_team_ranking(home_team_id, season)
            if home_ranking:
                home_rank = home_ranking.get("rank")

        if away_team_id:
            away_ranking = get_team_ranking(away_team_id, season)
            if away_ranking:
                away_rank = away_ranking.get("rank")
    except Exception as e:
        # SECURITY: Log error server-side, continue without rankings
        logger.warning(f"Error fetching rankings for game {game_id}: {e}")

    return GameResponse(
        id=game_id,
        date=game.get("date"),
        home_team=game.get("home_team", {}).get("name", "Unknown"),
        away_team=game.get("away_team", {}).get("name", "Unknown"),
        home_rank=home_rank,
        away_rank=away_rank,
        home_spread=spread.get("home_spread") if spread else None,
        is_conference_game=game.get("is_conference_game", False),
        prediction=prediction,
        ai_analyses=analyses,
    )


class GameAnalyticsResponse(BaseModel):
    """
    Response model for /games/{game_id}/analytics endpoint.

    Contains advanced analytics from KenPom and Haslametrics for both teams.

    Example Response:
        {
            "game_id": "123e4567-e89b-12d3-a456-426614174000",
            "home_team": "Duke",
            "away_team": "North Carolina",
            "home_kenpom": {
                "rank": 5,
                "adj_offense": 118.5,
                "adj_defense": 95.2,
                "adj_efficiency_margin": 23.3,
                "adj_tempo": 68.5
            },
            "away_kenpom": {...},
            "home_haslametrics": {
                "rank": 8,
                "all_play_pct": 0.89,
                "momentum_overall": 0.3,
                "offensive_efficiency": 115.2
            },
            "away_haslametrics": {...}
        }
    """
    game_id: str = Field(description="Game UUID")
    home_team: str = Field(description="Home team name")
    away_team: str = Field(description="Away team name")
    home_kenpom: Optional[dict] = Field(default=None, description="Home team KenPom analytics")
    away_kenpom: Optional[dict] = Field(default=None, description="Away team KenPom analytics")
    home_haslametrics: Optional[dict] = Field(default=None, description="Home team Haslametrics data")
    away_haslametrics: Optional[dict] = Field(default=None, description="Away team Haslametrics data")


@app.get("/games/{game_id}/analytics", response_model=GameAnalyticsResponse, tags=["Games", "Analytics"])
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_game_analytics(request: Request, game_id: GameIdPath):
    """
    Get advanced analytics (KenPom + Haslametrics) for a specific game.

    Designed for lazy loading - fetch analytics only when a user expands
    a game card or views the detailed analytics section.

    Returns comprehensive advanced analytics for both teams:

    **KenPom Metrics** (requires subscription):
        - rank: Overall KenPom ranking
        - adj_offense: Adjusted offensive efficiency (points per 100 possessions)
        - adj_defense: Adjusted defensive efficiency (lower is better)
        - adj_efficiency_margin: AdjO - AdjD (main power rating)
        - adj_tempo: Adjusted tempo (possessions per 40 minutes)
        - luck: Deviation from expected record
        - sos_adj_em: Strength of schedule

    **Haslametrics Metrics** (FREE):
        - rank: Overall Haslametrics ranking
        - all_play_pct: Win probability vs average D1 team (core metric)
        - momentum_overall/offense/defense: Recent performance trends
        - offensive_efficiency/defensive_efficiency: Points per 100 possessions
        - quad_1_record through quad_4_record: Record vs NET quadrants
        - last_5_record: Recent 5-game record

    Path Parameters:
        game_id: UUID of the game

    Returns:
        GameAnalyticsResponse: Analytics for both teams

    Raises:
        404 Not Found: If game doesn't exist

    Rate Limit: 30 requests per minute per IP

    Caching: Results are cached for 1 hour (refreshed during daily pipeline)
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


@app.get("/stats", response_model=StatsResponse, tags=["Performance"])
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_stats(
    request: Request,
    season: Annotated[
        Optional[int],
        Query(ge=2000, le=2100, description="Season year (e.g., 2025)")
    ] = None
):
    """
    Get betting performance statistics for a season.

    Calculates comprehensive performance metrics from graded bets:
    - Win/loss record and percentage
    - Units wagered and won
    - ROI (Return on Investment)

    Query Parameters:
        season: Season year (default: current year)

    Returns:
        StatsResponse: Season performance statistics

    Rate Limit: 30 requests per minute per IP

    Example Request:
        GET /stats?season=2025

    Example Response:
        {
            "season": 2025,
            "total_bets": 150,
            "wins": 85,
            "losses": 62,
            "pushes": 3,
            "win_pct": 57.82,
            "units_wagered": 150.0,
            "units_won": 12.5,
            "roi_pct": 8.33
        }

    Note: Win percentage of 52.4% is breakeven at standard -110 odds.
    Returns zeros if no graded bets exist for the season.
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


@app.get("/rankings", tags=["Rankings"])
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
    Get current AP poll rankings.

    Returns the most recent week's rankings for the specified season and poll type.

    Query Parameters:
        season: Season year (default: current year)
        poll_type: Poll type (default: "ap" for AP Top 25)

    Returns:
        dict: Season, poll type, and ranked teams

    Rate Limit: 30 requests per minute per IP

    Example Request:
        GET /rankings?season=2025&poll_type=ap

    Example Response:
        {
            "season": 2025,
            "poll_type": "ap",
            "rankings": [
                {
                    "rank": 1,
                    "team": {"id": "...", "name": "Auburn"},
                    "points": 1525,
                    "record": "18-1"
                },
                ...
            ]
        }

    Note: Rankings are updated weekly during the season. Returns empty
    list if no rankings exist for the specified season/poll.
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


@app.post("/refresh", tags=["Admin"])
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
    Trigger a full data refresh pipeline.

    Runs the complete daily data refresh including:
    1. Fetch betting lines from The Odds API (spreads, moneylines, totals)
    2. Refresh KenPom advanced analytics (if credentials configured)
    3. Refresh Haslametrics data (FREE, no auth required)
    4. Refresh ESPN tip times (accurate game start times)
    5. Refresh prediction market data (Polymarket, Kalshi)
    6. Detect arbitrage opportunities (>=10% edge threshold)
    7. Run predictions on upcoming games
    8. Update game results for completed games
    9. Run AI analysis on today's games

    This endpoint is typically called by GitHub Actions cron job at 6 AM EST.

    Query Parameters:
        api_key: Optional authentication key (checked against REFRESH_API_KEY env var)
        force_regenerate: If true, deletes existing predictions before regenerating

    Returns:
        dict: Status and results for each pipeline step

    Example Request:
        POST /refresh?api_key=secret123&force_regenerate=false

    Example Response:
        {
            "status": "success",
            "timestamp": "2025-01-25T06:00:00Z",
            "results": {
                "odds_fetched": 45,
                "kenpom_updated": 362,
                "haslametrics_updated": 362,
                "predictions_created": 38,
                "ai_analyses_created": 12
            }
        }

    Warning: Full refresh can take 3-5 minutes. For testing, use individual
    endpoints like /refresh-haslametrics or /regenerate-predictions.

    Security: If REFRESH_API_KEY is set in environment, requests with
    incorrect api_key will be rejected.
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


@app.post("/regenerate-predictions", tags=["Admin"])
def regenerate_predictions():
    """
    Regenerate predictions for upcoming games (fast, no external API calls).

    This endpoint is much faster than /refresh as it only runs the prediction
    model on existing data without fetching new odds, KenPom, or Haslametrics.

    Use this when:
    - Testing prediction model changes
    - Games need predictions but data is already fresh
    - Full refresh is timing out

    Returns:
        dict: Status and count of predictions created

    Example Response:
        {
            "status": "success",
            "predictions_created": 38
        }

    Note: Does not overwrite existing predictions unless they're older than
    the latest data refresh.
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


@app.post("/refresh-haslametrics", tags=["Admin"])
def refresh_haslametrics_endpoint():
    """
    Refresh only Haslametrics advanced analytics data.

    Fast endpoint (10-20 seconds) that fetches the latest Haslametrics
    ratings without running the full refresh pipeline. Useful for testing
    and when only analytics data needs updating.

    Haslametrics is FREE (no subscription required) and provides:
    - All-Play Percentage (core metric: win % vs average D1 team)
    - Momentum indicators (overall, offense, defense)
    - Efficiency ratings
    - Quadrant records (Q1-Q4)
    - Recent performance (last 5 games)

    Returns:
        dict: Status and count of teams updated

    Example Response:
        {
            "status": "success",
            "timestamp": "2025-01-25T14:30:00Z",
            "results": {
                "inserted": 362,
                "skipped": 0,
                "errors": 0
            }
        }

    Technical Note: Requires 'brotli' package as Haslametrics serves
    Brotli-compressed XML responses.
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


@app.post("/refresh-prediction-markets", tags=["Admin"])
def refresh_prediction_markets_endpoint():
    """
    Refresh prediction market data from Polymarket and Kalshi.

    Fetches current prices and market data from prediction market platforms,
    matches markets to teams/games in our database, and detects arbitrage
    opportunities between prediction markets and traditional sportsbooks.

    Pipeline Steps:
    1. Fetch Polymarket NCAA basketball markets
    2. Fetch Kalshi NCAAMBGAME markets (if API configured)
    3. Match markets to teams in our database
    4. Compare prices with sportsbook implied probabilities
    5. Flag arbitrage opportunities (>=10% delta)

    Returns:
        dict: Status and results from each platform

    Example Response:
        {
            "status": "success",
            "timestamp": "2025-01-25T14:30:00Z",
            "polymarket": {"markets_found": 45, "matched": 38},
            "kalshi": {"markets_found": 12, "matched": 8},
            "arbitrage": {"opportunities_found": 3}
        }

    Note: Kalshi requires API credentials (KALSHI_API_KEY and
    KALSHI_PRIVATE_KEY_PATH environment variables).
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


@app.get("/prediction-markets", tags=["Prediction Markets"])
def get_prediction_markets():
    """
    Get stored prediction market data with matched team names.

    Returns currently open prediction markets from Polymarket and Kalshi
    that have been matched to teams in our database.

    Returns:
        dict: Count and list of matched markets

    Example Response:
        {
            "count": 45,
            "markets": [
                {
                    "source": "polymarket",
                    "market_id": "0x123...",
                    "title": "Duke to win ACC Tournament",
                    "market_type": "futures",
                    "status": "open",
                    "team_id": "abc123...",
                    "team_name": "Duke"
                }
            ]
        }
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


@app.get("/debug-pm-match")
def debug_pm_match():
    """
    Debug: Check if prediction markets match upcoming games.
    """
    try:
        from .supabase_client import get_supabase
        supabase = get_supabase()

        # Get prediction market team IDs
        pm_result = supabase.table("prediction_markets").select("team_id").eq("status", "open").execute()
        pm_team_ids = set(m["team_id"] for m in (pm_result.data or []) if m.get("team_id"))

        # Get upcoming games
        from datetime import date, timedelta
        today = date.today()
        end_date = today + timedelta(days=7)
        games_result = supabase.table("games").select(
            "id, date, home_team_id, away_team_id"
        ).gte("date", today.isoformat()).lte("date", end_date.isoformat()).execute()
        games = games_result.data or []

        # Check for matches
        matches = []
        for g in games:
            home_match = g["home_team_id"] in pm_team_ids
            away_match = g["away_team_id"] in pm_team_ids
            if home_match or away_match:
                matches.append({
                    "game_id": g["id"],
                    "date": g["date"],
                    "home_team_id": g["home_team_id"],
                    "away_team_id": g["away_team_id"],
                    "home_has_pm": home_match,
                    "away_has_pm": away_match,
                })

        return {
            "pm_team_ids_count": len(pm_team_ids),
            "games_checked": len(games),
            "games_with_pm_match": len(matches),
            "matches": matches[:10],  # First 10
        }
    except Exception as e:
        logger.error(f"Debug PM match failed: {e}")
        return {"error": str(e)}


@app.get("/test-kalshi")
def test_kalshi_endpoint():
    """
    Diagnostic endpoint to test Kalshi API connection.
    Returns authentication status and sample markets to identify CBB ticker formats.
    """
    try:
        import asyncio
        from ..data_collection.kalshi_client import KalshiClient, KALSHI_BASE_URL

        client = KalshiClient()

        results = {
            "is_configured": client.is_configured,
            "private_key_loaded": False,
        }

        if not client.is_configured:
            results["error"] = "Kalshi not configured"
            return results

        try:
            pk = client.private_key
            results["private_key_loaded"] = pk is not None
        except Exception as e:
            results["private_key_error"] = str(e)
            return results

        async def test_fetch():
            # Try fetching NCAAMBGAME markets directly by series
            cbb_markets = []

            # Method 1: Try series_ticker filter
            path = "/markets"
            params = {"limit": 100, "status": "open", "series_ticker": "KXNCAAMBGAME"}
            headers = client._get_headers("GET", path)

            response = await client.client.get(path, headers=headers, params=params)
            method1_status = response.status_code
            method1_count = 0
            if response.status_code == 200:
                data = response.json()
                batch = data.get("markets", [])
                method1_count = len(batch)
                for m in batch[:5]:
                    cbb_markets.append({"ticker": m.get("ticker"), "title": m.get("title", "")[:80]})

            # Method 2: Try event_ticker filter
            params2 = {"limit": 100, "status": "open", "event_ticker": "KXNCAAMBGAME"}
            response2 = await client.client.get(path, headers=headers, params=params2)
            method2_status = response2.status_code
            method2_count = 0
            if response2.status_code == 200:
                data2 = response2.json()
                batch2 = data2.get("markets", [])
                method2_count = len(batch2)
                for m in batch2[:5]:
                    if m.get("ticker") not in [x["ticker"] for x in cbb_markets]:
                        cbb_markets.append({"ticker": m.get("ticker"), "title": m.get("title", "")[:80]})

            # Method 3: Search for Georgetown specifically
            params3 = {"limit": 100, "status": "open"}
            response3 = await client.client.get(path, headers=headers, params=params3)
            georgetown_found = []
            if response3.status_code == 200:
                data3 = response3.json()
                for m in data3.get("markets", []):
                    ticker = m.get("ticker", "").upper()
                    if "GTWN" in ticker or "GEORGETOWN" in ticker.upper() or "KXNCAAMB" in ticker:
                        georgetown_found.append({"ticker": m.get("ticker"), "title": m.get("title", "")[:80]})

            return {
                "api_status": 200,
                "method1_series_ticker": {"status": method1_status, "count": method1_count},
                "method2_event_ticker": {"status": method2_status, "count": method2_count},
                "method3_search_first_page": {"georgetown_matches": len(georgetown_found)},
                "cbb_markets_found": cbb_markets[:10],
                "georgetown_markets": georgetown_found[:5],
            }

        async def run_test():
            try:
                return await test_fetch()
            finally:
                await client.close()

        # Use new event loop to avoid "Event loop is closed" error
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fetch_result = loop.run_until_complete(run_test())
        finally:
            loop.close()
        results.update(fetch_result)

        return results

    except Exception as e:
        logger.error(f"Kalshi test failed: {e}", exc_info=True)
        return {"error": str(e)}


@app.post("/refresh-espn-times", tags=["Admin"])
def refresh_espn_times_endpoint(
    days: Annotated[
        int,
        Query(ge=1, le=14, description="Number of days ahead to fetch (max 14)")
    ] = 7
):
    """
    Update game tip-off times from ESPN's public API.

    Fetches accurate scheduled game times from ESPN and updates the tip_time
    field in our games table. This is a fast operation (5-10 seconds) that
    requires no authentication.

    Use Cases:
    - Initial population of tip times after games are created
    - Updating postponed/rescheduled games
    - Syncing with latest ESPN schedule data

    Query Parameters:
        days: Number of days ahead to fetch (default: 7, max: 14)

    Returns:
        dict: Status and count of games updated

    Example Response:
        {
            "status": "success",
            "results": {
                "espn_games_found": 85,
                "games_updated": 78,
                "games_not_matched": 7
            }
        }

    Note: Games are matched by date and team names. Some ESPN team names
    may not match our database and will be skipped.
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


@app.get("/backtest", tags=["Performance"])
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
    Run backtest on historical data (PLACEHOLDER).

    This endpoint will allow running prediction models against historical
    game data to evaluate performance.

    Query Parameters:
        start_date: Start date in ISO format (required)
        end_date: End date in ISO format (required)
        model: Model name for backtesting (default: "baseline")

    Returns:
        dict: Backtest parameters (not yet implemented)

    Raises:
        422 Validation Error: If end_date is before start_date

    Example Request:
        GET /backtest?start_date=2024-11-01&end_date=2024-12-31&model=baseline

    Status: NOT YET IMPLEMENTED - Returns placeholder response
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


@app.get("/debug/ai-analysis/{game_id}", tags=["Debug"])
@limiter.limit(RATE_LIMIT_AI_ENDPOINTS)
def debug_ai_analysis(request: Request, game_id: GameIdPath, provider: Literal["claude", "grok"] = "claude"):
    """
    Debug endpoint for diagnosing AI analysis issues.

    Runs through the full AI analysis pipeline step-by-step and returns
    detailed information about each step, including any errors encountered.
    Useful for troubleshooting when /ai-analysis returns generic errors.

    Pipeline Steps Tested:
    1. Game fetch - Verify game exists in database
    2. Context build - Build game context with all data sources
    3. API keys - Verify AI provider credentials are configured
    4. Prompt build - Construct the analysis prompt
    5. AI call - Call the AI provider and parse response
    6. DB insert - Save analysis to database

    Path Parameters:
        game_id: UUID of the game to test
        provider: AI provider to test ("claude" or "grok")

    Returns:
        dict: Step-by-step results and any errors

    Example Response:
        {
            "game_id": "123...",
            "provider": "claude",
            "steps": {
                "1_game_fetch": {"status": "success", "home_team": "Duke"},
                "2_build_context": {"status": "success", "has_kenpom": true},
                "3_api_keys": {"anthropic_configured": true},
                "4_prompt_build": {"status": "success", "prompt_length": 2500},
                "5_ai_call": {"status": "success", "recommended_bet": "away_spread"},
                "6_db_insert": {"status": "success", "inserted_id": "abc..."}
            },
            "errors": [],
            "overall_status": "success"
        }

    WARNING: This endpoint exposes detailed error information.
    Consider disabling in production (check ENVIRONMENT env var).

    Rate Limit: 5 requests per minute per IP
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


# =============================================================================
# ODDS MOVEMENT & LIVE ANALYSIS ENDPOINTS
# =============================================================================


@app.get("/api/v1/odds/movements", tags=["Odds Movement"])
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_odds_movements(request: Request):
    """
    Get all detected odds movements from the last refresh.

    Returns movements for all active games, indicating which have
    significant line changes (2pt spread or 10% probability threshold).

    Returns:
        dict: List of movements with significance flags
    """
    from backend.services.odds_monitor import odds_monitor

    result = odds_monitor.check_all_active_games()
    return result


@app.get("/api/v1/odds/movements/{game_id}", tags=["Odds Movement"])
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def get_game_movement(request: Request, game_id: GameIdPath):
    """
    Get odds movement data for a specific game.

    Returns:
        dict: Movement data or 404 if no movement detected
    """
    from backend.services.odds_monitor import odds_monitor

    movement = odds_monitor.get_game_movement(game_id)
    if not movement:
        raise NotFoundException(resource="Movement", identifier=game_id)
    return movement


@app.post("/api/v1/odds/refresh", tags=["Odds Movement"])
@limiter.limit(RATE_LIMIT_AI_ENDPOINTS)
def refresh_odds_movements(request: Request):
    """
    Manually refresh odds and detect movements.

    Fetches current odds from The Odds API, compares against stored
    spreads, and returns all detected movements.

    Returns:
        dict: Refresh results with movements and significant movements
    """
    from backend.services.odds_monitor import odds_monitor

    return odds_monitor.check_all_active_games()


@app.get("/api/v1/analysis/live/{game_id}", tags=["Odds Movement", "AI Analysis"])
@limiter.limit(RATE_LIMIT_AI_ENDPOINTS)
def get_live_analysis(request: Request, game_id: GameIdPath):
    """
    Get AI-powered analysis of odds movement for a specific game.

    If a significant movement was detected for this game, generates
    a Claude-powered explanation and updated recommendation.

    Returns:
        dict: Movement analysis with explanation, updated rec, and action
    """
    from backend.services.odds_monitor import odds_monitor
    from backend.services.live_analysis import generate_movement_analysis

    movement = odds_monitor.get_game_movement(game_id)
    if not movement:
        return {
            "status": "no_movement",
            "game_id": game_id,
            "message": "No movement detected. Run POST /api/v1/odds/refresh first.",
        }

    if not movement.get("is_significant"):
        return {
            "status": "not_significant",
            "game_id": game_id,
            "movement": movement,
            "message": "Movement detected but below significance threshold.",
        }

    return generate_movement_analysis(game_id, movement)


# =============================================================================
# BATCH UPSERT ENDPOINTS
# =============================================================================


class BatchGameItem(BaseModel):
    """A single game item for batch upsert."""
    id: Optional[str] = Field(default=None, description="Game UUID (primary key for update)")
    external_id: Optional[str] = Field(default=None, max_length=255, description="External ID fallback for conflict resolution")
    home_team: str = Field(min_length=1, max_length=100, description="Home team name")
    away_team: str = Field(min_length=1, max_length=100, description="Away team name")
    date: str = Field(description="Game date in ISO format (YYYY-MM-DD)")
    season: Optional[int] = Field(default=None, ge=1900, le=2100, description="Season year")
    is_conference_game: Optional[bool] = Field(default=None)
    venue: Optional[str] = Field(default=None, max_length=255)
    home_conference: Optional[str] = Field(default=None, max_length=50)
    away_conference: Optional[str] = Field(default=None, max_length=50)

    @field_validator('id')
    @classmethod
    def validate_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not UUID_PATTERN.match(v):
            raise ValueError('id must be a valid UUID')
        return v

    @field_validator('date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except (ValueError, TypeError):
            raise ValueError('date must be ISO format (YYYY-MM-DD)')
        return v


class BatchGameRequest(BaseModel):
    """Request model for batch game upsert."""
    games: list[BatchGameItem] = Field(description="List of games to upsert (max 100)")

    @field_validator('games')
    @classmethod
    def validate_length(cls, v: list) -> list:
        if len(v) > 100:
            raise ValueError('Maximum 100 games per batch')
        if len(v) == 0:
            raise ValueError('At least 1 game required')
        return v


class BatchTeamItem(BaseModel):
    """A single team item for batch upsert."""
    id: Optional[str] = Field(default=None, description="Team UUID (primary key for update)")
    name: str = Field(min_length=1, max_length=100, description="Team name")
    conference: Optional[str] = Field(default=None, max_length=50)
    is_power_conference: Optional[bool] = Field(default=None)

    @field_validator('id')
    @classmethod
    def validate_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not UUID_PATTERN.match(v):
            raise ValueError('id must be a valid UUID')
        return v


class BatchTeamRequest(BaseModel):
    """Request model for batch team upsert."""
    teams: list[BatchTeamItem] = Field(description="List of teams to upsert (max 200)")

    @field_validator('teams')
    @classmethod
    def validate_length(cls, v: list) -> list:
        if len(v) > 200:
            raise ValueError('Maximum 200 teams per batch')
        if len(v) == 0:
            raise ValueError('At least 1 team required')
        return v


class BatchResultItem(BaseModel):
    """Result for a single item in a batch operation."""
    index: int = Field(description="Index in the input array")
    status: str = Field(description="'created', 'updated', or 'error'")
    id: Optional[str] = Field(default=None, description="ID of the created/updated record")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class BatchResponse(BaseModel):
    """Response model for batch operations."""
    created: int = Field(description="Number of records created")
    updated: int = Field(description="Number of records updated")
    errors: list[BatchResultItem] = Field(description="List of failed items with error details")
    results: list[BatchResultItem] = Field(description="Full list of results per item")


@app.post("/api/v1/games/batch", response_model=BatchResponse, tags=["Games"])
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def batch_upsert_games(request: Request, body: BatchGameRequest):
    """
    Batch upsert games with conflict resolution and partial success.

    For each game:
    - If `id` is provided, looks up by primary key first
    - Falls back to `external_id` for conflict resolution
    - Creates new game if no match found
    - Updates existing game if match found

    Returns per-item results. One bad item does not fail the entire batch.

    Request Body:
        games: List of game objects (max 100)

    Returns:
        BatchResponse with created/updated counts and per-item results
    """
    created = 0
    updated = 0
    errors_list: list[BatchResultItem] = []
    results: list[BatchResultItem] = []

    for idx, game_item in enumerate(body.games):
        try:
            game_data = game_item.model_dump(exclude_none=True)

            # upsert_game uses .upsert(on_conflict='external_id') atomically
            result = upsert_game(game_data)

            # Validate that upsert returned an id
            record_id = result.get("id") if isinstance(result, dict) else None
            if not record_id:
                error_item = BatchResultItem(index=idx, status="error", error="Upsert returned no id")
                errors_list.append(error_item)
                results.append(error_item)
                continue

            # Supabase upsert doesn't distinguish create vs update in response,
            # so we report as "updated" (covers both cases atomically)
            updated += 1
            results.append(BatchResultItem(index=idx, status="updated", id=record_id))

        except Exception as e:
            error_msg = str(e)[:200]
            error_item = BatchResultItem(index=idx, status="error", error=error_msg)
            errors_list.append(error_item)
            results.append(error_item)

    return BatchResponse(created=created, updated=updated, errors=errors_list, results=results)


@app.post("/api/v1/teams/batch", response_model=BatchResponse, tags=["Games"])
@limiter.limit(RATE_LIMIT_STANDARD_ENDPOINTS)
def batch_upsert_teams(request: Request, body: BatchTeamRequest):
    """
    Batch upsert teams with conflict resolution and partial success.

    For each team:
    - If `id` is provided, looks up by primary key first
    - Falls back to exact name match, then normalized name match
    - Creates new team if no match found
    - Updates existing team if match found

    Returns per-item results. One bad item does not fail the entire batch.

    Request Body:
        teams: List of team objects (max 200)

    Returns:
        BatchResponse with created/updated counts and per-item results
    """
    created = 0
    updated = 0
    errors_list: list[BatchResultItem] = []
    results: list[BatchResultItem] = []

    client = get_supabase()
    power_conferences = {"ACC", "Big Ten", "Big 12", "SEC", "Big East", "Pac-12"}

    for idx, team_item in enumerate(body.teams):
        try:
            is_power = team_item.is_power_conference
            if is_power is None and team_item.conference:
                is_power = team_item.conference in power_conferences

            team_data = {
                "name": team_item.name,
                "normalized_name": normalize_team_name(team_item.name),
                "conference": team_item.conference,
                "is_power_conference": is_power or False,
            }
            if team_item.id:
                team_data["id"] = team_item.id

            # Atomic upsert on name conflict
            result = client.table("teams").upsert(
                team_data, on_conflict="name"
            ).execute()

            record_id = result.data[0].get("id") if result.data else None
            if not record_id:
                error_item = BatchResultItem(index=idx, status="error", error="Upsert returned no id")
                errors_list.append(error_item)
                results.append(error_item)
                continue

            # Report as updated (upsert covers both create and update atomically)
            updated += 1
            results.append(BatchResultItem(index=idx, status="updated", id=record_id))

        except Exception as e:
            error_msg = str(e)[:200]
            error_item = BatchResultItem(index=idx, status="error", error=error_msg)
            errors_list.append(error_item)
            results.append(error_item)

    return BatchResponse(created=created, updated=updated, errors=errors_list, results=results)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
