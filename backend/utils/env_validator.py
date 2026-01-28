"""
Startup environment validation.
Logs configuration status without exposing secret values.
"""
import os
import logging

logger = logging.getLogger("conference_contrarian.config")


def mask_key(value: str | None) -> str:
    """Show first 4 and last 4 chars of a key, mask the rest."""
    if not value:
        return "NOT SET"
    if len(value) <= 12:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def validate_environment() -> dict[str, bool]:
    """
    Validate environment variables at startup.
    Returns dict of service -> configured status.
    Logs warnings for missing critical variables.
    """
    logger.info("=" * 50)
    logger.info("ENVIRONMENT VALIDATION")
    logger.info("=" * 50)

    status = {}

    # Critical: Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    status["supabase"] = bool(supabase_url and supabase_key)
    if status["supabase"]:
        logger.info(f"Supabase: OK ({supabase_url[:30]}...)")
    else:
        logger.error("Supabase: MISSING - database operations will fail")

    # AI Services
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    status["claude"] = bool(anthropic_key)
    if status["claude"]:
        logger.info(f"Claude API: OK ({mask_key(anthropic_key)})")
    else:
        logger.warning("Claude API: NOT CONFIGURED - Claude analysis disabled")

    grok_key = os.getenv("GROK_API_KEY")
    status["grok"] = bool(grok_key)
    if status["grok"]:
        logger.info(f"Grok API: OK ({mask_key(grok_key)})")
    else:
        logger.warning("Grok API: NOT CONFIGURED - Grok analysis disabled")

    if not status["claude"] and not status["grok"]:
        logger.error("NO AI PROVIDERS CONFIGURED - AI analysis completely disabled")

    # Data sources
    odds_key = os.getenv("ODDS_API_KEY")
    status["odds_api"] = bool(odds_key)
    if status["odds_api"]:
        logger.info(f"Odds API: OK ({mask_key(odds_key)})")
    else:
        logger.warning("Odds API: NOT CONFIGURED - live odds unavailable")

    kenpom_email = os.getenv("KENPOM_EMAIL")
    status["kenpom"] = bool(kenpom_email)
    if status["kenpom"]:
        logger.info("KenPom: Credentials configured")
    else:
        logger.info("KenPom: Not configured (using cached data only)")

    # Security
    refresh_key = os.getenv("REFRESH_API_KEY")
    status["refresh_auth"] = bool(refresh_key)
    if not status["refresh_auth"]:
        logger.warning("REFRESH_API_KEY: NOT SET - cron endpoints unprotected")

    allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
    if allowed_origins:
        origins_count = len(allowed_origins.split(","))
        logger.info(f"CORS: {origins_count} allowed origin(s)")
    else:
        logger.warning("ALLOWED_ORIGINS: NOT SET - using restrictive defaults")

    # Summary
    configured = sum(1 for v in status.values() if v)
    total = len(status)
    logger.info(f"Services configured: {configured}/{total}")
    logger.info("=" * 50)

    return status
