# AI Analysis System Documentation

This document describes the AI-powered game analysis system in Conference Contrarian, including the dual-provider architecture (Claude and Grok), API endpoints, data flow, prompt engineering strategy, and error handling.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [AI Provider Integration](#ai-provider-integration)
3. [API Endpoints](#api-endpoints)
4. [Request/Response Schemas](#requestresponse-schemas)
5. [Data Flow](#data-flow)
6. [Prompt Engineering Strategy](#prompt-engineering-strategy)
7. [Confidence Scoring Logic](#confidence-scoring-logic)
8. [Error Handling](#error-handling)
9. [Security Considerations](#security-considerations)

---

## Architecture Overview

The AI Analysis system provides betting recommendations for NCAA basketball games using large language models. The system supports multiple AI providers to enable comparison and consensus-building.

### High-Level Architecture Diagram

```
+-------------------+     +-------------------+     +-------------------+
|    Frontend       |     |   Backend API     |     |   AI Providers    |
|   (Next.js)       |     |   (FastAPI)       |     |                   |
+-------------------+     +-------------------+     +-------------------+
         |                         |                         |
         |  POST /ai-analysis      |                         |
         |------------------------>|                         |
         |  {game_id, provider}    |                         |
         |                         |                         |
         |                         |  1. Fetch Game Context  |
         |                         |<----------------------->| Supabase
         |                         |                         |
         |                         |  2. Build Prompt        |
         |                         |                         |
         |                         |  3. Call AI API         |
         |                         |------------------------>| Claude/Grok
         |                         |                         |
         |                         |  4. Parse Response      |
         |                         |<------------------------|
         |                         |                         |
         |                         |  5. Store Analysis      |
         |                         |------------------------>| Supabase
         |                         |                         |
         |  JSON Response          |                         |
         |<------------------------|                         |
         |                         |                         |
+-------------------+     +-------------------+     +-------------------+
```

### Component Overview

| Component | Location | Purpose |
|-----------|----------|---------|
| `AIAnalysisButton.tsx` | `frontend/src/components/` | User interface for triggering AI analysis |
| `ai_service.py` | `backend/api/` | Core AI analysis logic and provider integration |
| `main.py` | `backend/api/` | FastAPI endpoints including `/ai-analysis` |
| `supabase_client.py` | `backend/api/` | Database operations for storing/retrieving analyses |
| `ai_analysis` table | Supabase | Persistent storage for analysis results |

---

## AI Provider Integration

The system supports two AI providers, each accessed through their respective APIs:

### Claude (Anthropic)

- **Provider ID:** `claude`
- **Model:** `claude-sonnet-4-20250514`
- **API:** Anthropic Python SDK (`anthropic`)
- **Base URL:** `https://api.anthropic.com` (default)

```python
# Initialization (from ai_service.py)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# API Call
response = claude_client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)
```

### Grok (xAI)

- **Provider ID:** `grok`
- **Model:** `grok-3`
- **API:** OpenAI-compatible SDK (`openai`)
- **Base URL:** `https://api.x.ai/v1`

```python
# Initialization (from ai_service.py)
grok_client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")

# API Call
response = grok_client.chat.completions.create(
    model="grok-3",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=1024
)
```

### Provider Selection

The frontend allows users to select which provider to use via a toggle:

```typescript
// From AIAnalysisButton.tsx
const [selectedProvider, setSelectedProvider] = useState<AIProvider>('claude');
```

---

## API Endpoints

### POST `/ai-analysis`

Generates AI-powered betting analysis for a specific game.

**Rate Limit:** 5 requests per minute per IP (AI endpoint tier)

**Request Headers:**
```
Content-Type: application/json
Accept: application/json
```

**Request Body:**
```json
{
  "game_id": "uuid-format-string",
  "provider": "claude" | "grok"
}
```

**Successful Response (200):**
```json
{
  "game_id": "123e4567-e89b-12d3-a456-426614174000",
  "provider": "claude",
  "recommended_bet": "home_spread",
  "confidence_score": 0.72,
  "key_factors": [
    "Home team has +8.5 KenPom efficiency margin advantage",
    "Away team on third road game in 6 days",
    "Strong momentum indicators favor home team"
  ],
  "reasoning": "Duke's KenPom AdjEM of +25.3 vs Carolina's +18.7 suggests a 6-7 point true margin...",
  "created_at": "2025-01-23T12:00:00Z"
}
```

**Error Response (4xx/5xx):**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "game_id must be a valid UUID"
  },
  "request_id": "abc12345"
}
```

### GET `/debug/ai-analysis/{game_id}`

Debug endpoint for diagnosing AI analysis issues. Returns step-by-step execution details.

**Warning:** Exposes internal error details - intended for development/debugging only.

**Query Parameters:**
- `provider`: `claude` | `grok` (default: `claude`)

**Response:**
```json
{
  "game_id": "...",
  "provider": "claude",
  "steps": {
    "1_game_fetch": {"status": "success", "home_team": "Duke", "away_team": "UNC"},
    "2_build_context": {"status": "success", "has_kenpom": true, "has_spread": true},
    "3_api_keys": {"anthropic_configured": true, "grok_configured": true},
    "4_prompt_build": {"status": "success", "prompt_length": 2456},
    "5_ai_call": {"status": "success", "recommended_bet": "home_spread"},
    "6_db_insert": {"status": "success", "inserted_id": "..."}
  },
  "errors": [],
  "overall_status": "success"
}
```

---

## Request/Response Schemas

### AIAnalysisRequest (Pydantic Model)

```python
class AIAnalysisRequest(BaseModel):
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
```

### AIAnalysisResponse (Pydantic Model)

```python
class AIAnalysisResponse(BaseModel):
    game_id: str
    provider: str
    recommended_bet: str
    confidence_score: float
    key_factors: list[str]
    reasoning: str
    created_at: Optional[str] = None
```

### Database Schema (ai_analysis table)

```sql
CREATE TABLE ai_analysis (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  game_id UUID REFERENCES games(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  ai_provider TEXT NOT NULL,           -- 'claude', 'grok', 'openai'
  model_used TEXT,                     -- e.g., 'claude-sonnet-4-20250514'
  analysis_type TEXT NOT NULL,         -- 'matchup', 'edge_detection', etc.
  prompt_hash TEXT,                    -- MD5 hash of prompt for deduplication
  response TEXT,                       -- Full raw AI response
  structured_analysis JSONB,           -- Reserved for future structured data
  recommended_bet TEXT,                -- 'home_spread', 'away_ml', 'pass', etc.
  confidence_score DECIMAL(3,2),       -- 0.00 to 1.00
  key_factors TEXT[],                  -- Array of factor strings
  reasoning TEXT,                      -- AI's explanation
  tokens_used INTEGER                  -- API usage tracking
);
```

### TypeScript Types (Frontend)

```typescript
export interface AIAnalysis {
  id: string;
  game_id: string | null;
  created_at: string;
  ai_provider: AIProvider;
  model_used: string | null;
  analysis_type: string;
  prompt_hash: string | null;
  response: string | null;
  structured_analysis: Record<string, unknown> | null;
  recommended_bet: string | null;
  confidence_score: number | null;
  key_factors: string[] | null;
  reasoning: string | null;
  tokens_used: number | null;
}

export type AIProvider = 'claude' | 'grok' | 'openai';
```

---

## Data Flow

### Complete Data Flow Diagram

```
User Clicks "Run Analysis"
            |
            v
+------------------------+
| 1. Frontend Request    |
|   AIAnalysisButton.tsx |
+------------------------+
            |
            | POST /ai-analysis
            | {game_id, provider}
            v
+------------------------+
| 2. API Validation      |
|   main.py              |
|   - UUID format check  |
|   - Provider validation|
|   - Rate limit check   |
+------------------------+
            |
            v
+------------------------+
| 3. Build Game Context  |
|   ai_service.py        |
|   build_game_context() |
+------------------------+
            |
            | Queries Supabase:
            | - games (with team joins)
            | - spreads (latest)
            | - rankings (current week)
            | - kenpom_ratings (latest)
            | - haslametrics_ratings (latest)
            | - prediction_markets (if available)
            | - arbitrage_opportunities (if available)
            v
+------------------------+
| 4. Build Analysis      |
|    Prompt              |
|   build_analysis_      |
|   prompt()             |
+------------------------+
            |
            | Includes:
            | - Team matchup info
            | - Betting lines
            | - KenPom analytics
            | - Haslametrics analytics
            | - Prediction market data
            | - Analysis instructions
            v
+------------------------+
| 5. Call AI Provider    |
|   analyze_with_claude()|
|   analyze_with_grok()  |
+------------------------+
            |
            | HTTP Request to:
            | - api.anthropic.com (Claude)
            | - api.x.ai/v1 (Grok)
            v
+------------------------+
| 6. Parse AI Response   |
|   - Extract JSON       |
|   - Validate structure |
|   - Handle parse errors|
+------------------------+
            |
            v
+------------------------+
| 7. Store in Database   |
|   insert_ai_analysis() |
|   supabase_client.py   |
+------------------------+
            |
            | Stores:
            | - Full response text
            | - Parsed recommendations
            | - Confidence score
            | - Key factors
            | - Tokens used
            v
+------------------------+
| 8. Return to Frontend  |
|   AIAnalysisResponse   |
+------------------------+
            |
            v
User Sees Analysis Result
(Page refreshes to show new analysis)
```

### Context Building Detail

The `build_game_context()` function assembles all relevant data for the AI:

```python
def build_game_context(game_id: str) -> dict:
    """Build context object for AI analysis."""

    # Core game data
    game = get_game_by_id(game_id)
    spread = get_latest_spread(game_id)

    # Rankings for both teams
    home_ranking = get_team_ranking(game["home_team_id"], game["season"])
    away_ranking = get_team_ranking(game["away_team_id"], game["season"])

    # KenPom advanced analytics
    home_kenpom = get_team_kenpom(game["home_team_id"], game["season"])
    away_kenpom = get_team_kenpom(game["away_team_id"], game["season"])

    # Haslametrics analytics
    home_haslametrics = get_team_haslametrics(game["home_team_id"], game["season"])
    away_haslametrics = get_team_haslametrics(game["away_team_id"], game["season"])

    # Prediction market data
    prediction_markets = get_game_prediction_markets(game_id)
    arbitrage_opportunities = get_game_arbitrage_opportunities(game_id)

    return {
        "game_id": game_id,
        "date": game.get("date"),
        "home_team": game.get("home_team", {}).get("name"),
        "away_team": game.get("away_team", {}).get("name"),
        # ... all context fields
    }
```

---

## Prompt Engineering Strategy

The prompt is carefully structured to elicit consistent, actionable betting analysis.

### Prompt Structure

```
1. ROLE DEFINITION
   "You are an expert college basketball betting analyst..."

2. MATCHUP SECTION
   - Team names with rankings
   - Game date and venue
   - Neutral site indicator

3. BETTING LINES SECTION
   - Current spread
   - Moneylines (home and away)
   - Over/under total

4. KENPOM ANALYTICS (if available)
   - Adjusted efficiency margin
   - Adjusted offense/defense ratings
   - Tempo
   - Strength of schedule
   - Luck factor
   - Win-loss record

5. HASLAMETRICS ANALYTICS (if available)
   - Offensive/defensive efficiency
   - All-Play percentage
   - Momentum indicators
   - Quadrant records
   - Recent form (Last 5)

6. PREDICTION MARKET DATA (if available)
   - Market prices and volumes
   - Arbitrage signals with delta %

7. CONTEXT SECTION
   - Conference game indicator
   - Tournament game indicator

8. ANALYSIS INSTRUCTIONS
   - Specific factors to consider based on available data
   - Guidelines for cross-validation when multiple data sources exist

9. OUTPUT FORMAT SPECIFICATION
   - JSON schema definition
   - Field descriptions and constraints
```

### Dynamic Prompt Adaptation

The prompt adapts based on available data:

```python
# From build_analysis_prompt()

if has_kenpom and has_haslametrics:
    # Both analytics sources - comprehensive analysis
    analysis_points = """
    1. Cross-validate KenPom AdjEM vs Haslametrics efficiency
    2. Momentum indicators from Haslametrics
    3. All-Play % comparison as baseline win probability
    4. Tempo matchup implications
    5. Quadrant record context
    6. Luck factor regression analysis
    7. Recent form vs season-long metrics
    8. Line value alignment with both models
    """
elif has_kenpom:
    # KenPom only
    analysis_points = """
    1. KenPom efficiency differentials
    2. Tempo implications
    3. Strength of schedule context
    4. Luck factor regression
    5. Home court advantage
    6. Line value vs KenPom predicted margin
    """
elif has_haslametrics:
    # Haslametrics only
    analysis_points = """
    1. Haslametrics efficiency and All-Play %
    2. Momentum indicators
    3. Recent form (Last 5)
    4. Quadrant records context
    5. Home court advantage
    6. Line value vs Haslametrics rankings
    """
else:
    # Basic analysis without advanced analytics
    analysis_points = """
    1. Ranking differential
    2. Home court advantage
    3. Conference game dynamics
    4. Historical patterns
    5. Line value assessment
    """
```

### Required Output Format

The AI is instructed to return a specific JSON structure:

```json
{
    "recommended_bet": "home_spread | away_spread | home_ml | away_ml | over | under | pass",
    "confidence_score": 0.0-1.0,
    "key_factors": ["factor 1", "factor 2", "factor 3"],
    "reasoning": "2-3 sentence explanation"
}
```

### Prompt Guidelines for AI

The prompt includes specific instructions:
- Only recommend bets with positive expected value
- If no clear edge exists, recommend "pass"
- Confidence 0.5 = coin flip, 0.8+ = strong conviction
- Be specific about WHY value exists, not just team quality
- Lower confidence when KenPom and Haslametrics disagree
- Consider prediction market data for market sentiment
- Actionable arbitrage (>=10% delta) warrants serious consideration

---

## Confidence Scoring Logic

### AI-Generated Confidence

The AI provides a `confidence_score` from 0.0 to 1.0:

| Score Range | Interpretation |
|-------------|----------------|
| 0.0 - 0.50 | No edge / coin flip |
| 0.51 - 0.59 | Slight lean |
| 0.60 - 0.69 | Moderate confidence |
| 0.70 - 0.79 | Good confidence |
| 0.80 - 1.00 | High conviction |

### Heuristic-Based Quick Recommendations

For fallback scenarios without AI, heuristics generate quick picks:

```python
def get_quick_recommendation(context: dict) -> dict:
    """Quick betting recommendation using simple heuristics."""

    # Conference contrarian logic
    if is_conf and spread is not None:
        if home_rank and not away_rank:
            # Ranked home team vs unranked
            if home_rank <= 5 and spread <= -12:
                # Top 5 at big spread - underdog might cover
                return {
                    "recommended_bet": "away_spread",
                    "confidence_score": 0.58,
                    "reasoning": "Top 5 teams often don't cover large conference spreads..."
                }

    # Default: no clear edge
    return {
        "recommended_bet": "pass",
        "confidence_score": 0.5,
        "reasoning": "No clear edge detected"
    }
```

### Consensus Scoring (Dual Provider)

When both Claude and Grok analyze the same game:

```python
def analyze_both(self, game_id: str, save: bool = True) -> dict:
    """Run analysis with both Claude and Grok."""

    # Run both analyses
    results["claude"] = analyze_game(game_id, "claude", save)
    results["grok"] = analyze_game(game_id, "grok", save)

    # Build consensus
    if claude_rec == grok_rec and claude_rec != "pass":
        results["consensus"] = {
            "recommended_bet": claude_rec,
            "confidence_score": (
                results["claude"]["confidence_score"] +
                results["grok"]["confidence_score"]
            ) / 2,
            "reasoning": "Both AI models agree on this recommendation."
        }
    else:
        results["consensus"] = {
            "recommended_bet": "pass",
            "confidence_score": 0.5,
            "reasoning": "AI models disagree - no consensus recommendation."
        }
```

---

## Error Handling

### Frontend Error Handling

The `AIAnalysisButton` component implements comprehensive error handling:

```typescript
// Error categorization
type ErrorType = 'timeout' | 'network' | 'server' | 'api_limit' | 'unknown';

interface ErrorState {
  type: ErrorType;
  message: string;
  canRetry: boolean;
}

// Error parsing logic
function parseError(err: unknown, response?: Response, responseText?: string): ErrorState {
  // AbortError = timeout
  if (err instanceof Error && err.name === 'AbortError') {
    return { type: 'timeout', message: '...', canRetry: true };
  }

  // Network errors
  if (err instanceof TypeError && err.message.includes('fetch')) {
    return { type: 'network', message: '...', canRetry: true };
  }

  // HTTP 429 = rate limiting
  if (response?.status === 429) {
    return { type: 'api_limit', message: '...', canRetry: true };
  }

  // HTTP 5xx = server error
  if (response?.status >= 500) {
    return { type: 'server', message: '...', canRetry: true };
  }

  return { type: 'unknown', message: '...', canRetry: true };
}
```

### Backend Error Handling

#### API-Level Exceptions

```python
# Custom exception classes (from middleware.py)
class ApiException(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details

class ValidationException(ApiException):
    """400 Bad Request - Invalid input."""

class NotFoundException(ApiException):
    """404 Not Found."""

class ExternalApiException(ApiException):
    """502 Bad Gateway - External API failure."""

class RateLimitException(ApiException):
    """429 Too Many Requests."""
```

#### AI Analysis Endpoint Error Handling

```python
@app.post("/ai-analysis", response_model=AIAnalysisResponse)
def ai_analysis(request: Request, analysis_request: AIAnalysisRequest):
    try:
        result = analyze_game(analysis_request.game_id, analysis_request.provider)
        return AIAnalysisResponse(...)

    except ValueError as e:
        # User input error - return sanitized message
        raise ValidationException(
            message=str(e)[:100],
            details={"game_id": ..., "provider": ...}
        )

    except Exception as e:
        # Log full error server-side, return generic message
        logger.error(f"AI analysis failed: {e}", exc_info=True)
        raise ExternalApiException(
            service=f"AI/{analysis_request.provider}",
            message="AI analysis failed. Please try again later."
        )
```

#### Error Message Sanitization

The system sanitizes error messages to prevent API key leakage:

```python
# Patterns that might contain sensitive information
_SENSITIVE_PATTERNS = [
    r'sk-ant-api[a-zA-Z0-9_-]+',      # Anthropic API keys
    r'xai-[a-zA-Z0-9_-]+',            # Grok/xAI keys
    r'sk-[a-zA-Z0-9_-]{40,}',         # OpenAI-style keys
    r'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',  # JWT tokens
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',     # Emails
]

def _sanitize_error_message(error_msg: str) -> str:
    """Sanitize error messages to remove sensitive information."""
    sanitized = error_msg
    for pattern in _COMPILED_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)

    # Truncate long messages
    if len(sanitized) > 500:
        sanitized = sanitized[:500] + "... [truncated]"

    return sanitized
```

#### JSON Parsing Fallback

If the AI response isn't valid JSON:

```python
try:
    analysis = json.loads(response_text)
except json.JSONDecodeError:
    # Try to extract JSON from response
    json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
    if json_match:
        analysis = json.loads(json_match.group())
    else:
        # Fallback to default values
        analysis = {
            "recommended_bet": "pass",
            "confidence_score": 0.5,
            "key_factors": ["Unable to parse AI response"],
            "reasoning": response_text[:500],
        }
```

### Retry Logic

The frontend implements a retry mechanism:

```typescript
// Longer timeout for retries (up to 3 minutes)
const timeout = isRetry ? 180000 : 120000;

// Track retry count
if (isRetry) {
  setRetryCount(prev => prev + 1);
}

// Limit retries to 3 attempts
{error.canRetry && retryCount < 3 && (
  <button onClick={handleRetry}>
    Try Again ({retryCount}/3)
  </button>
)}
```

---

## Security Considerations

### API Key Protection

- Keys loaded from environment variables only
- Never logged or included in error messages
- Validated format before use
- Sanitized in any error output

```python
# API Keys - loaded from environment, never hardcoded
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
```

### Input Validation

- UUID format validation on all game IDs
- Provider limited to enum values (`claude` | `grok`)
- Pydantic models enforce schema validation

```python
UUID_PATTERN = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)

def _validate_uuid(value: str, field_name: str = "id") -> str:
    if not UUID_PATTERN.match(value):
        raise ValueError(f"Invalid {field_name} format")
    return value
```

### Rate Limiting

AI endpoints are rate-limited to prevent abuse:

```python
# Rate limit constants
RATE_LIMIT_AI_ENDPOINTS = "5/minute"       # Expensive AI analysis
RATE_LIMIT_STANDARD_ENDPOINTS = "30/minute" # Standard API

@app.post("/ai-analysis")
@limiter.limit(RATE_LIMIT_AI_ENDPOINTS)
def ai_analysis(request: Request, ...):
    ...
```

### CORS Configuration

Strict CORS policy to prevent unauthorized access:

```python
ALLOWED_ORIGINS = [
    "https://confcontrarian.com",
    "https://www.confcontrarian.com",
    "http://localhost:3000"  # Development only
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)
```

### Error Response Security

- Internal errors logged server-side only
- Generic messages returned to clients
- Request IDs for correlation without exposing details

```python
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"[{request_id}] Unhandled exception: {exc}")

    return JSONResponse(
        status_code=500,
        content=error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred",  # Generic message
            None,
            request_id
        )
    )
```

---

## Appendix: Environment Variables

Required for AI analysis functionality:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes (for Claude) | Anthropic API key for Claude |
| `GROK_API_KEY` | Yes (for Grok) | xAI API key for Grok |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `ALLOWED_ORIGINS` | Recommended | Comma-separated CORS origins |

---

## Appendix: Related Files

| File | Purpose |
|------|---------|
| `backend/api/ai_service.py` | Core AI analysis logic |
| `backend/api/main.py` | API endpoints |
| `backend/api/supabase_client.py` | Database operations |
| `backend/api/middleware.py` | Error handling, rate limiting |
| `backend/api/secrets_validator.py` | API key validation |
| `frontend/src/components/AIAnalysisButton.tsx` | UI component |
| `frontend/src/components/AIAnalysis.tsx` | Analysis display component |
| `frontend/src/lib/types.ts` | TypeScript type definitions |
| `supabase/migrations/20250118000000_initial_schema.sql` | Database schema |
