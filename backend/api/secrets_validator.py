"""
Secrets Validator Module for Conference Contrarian.

This module validates that all required secrets/API keys are properly configured
at application startup. It prevents the application from starting with missing
critical configuration and provides secure error handling.

SECURITY FEATURES:
- Never logs or exposes actual secret values
- Validates format without revealing contents
- Provides clear error messages for missing/invalid secrets
- Masks secrets in any error output
- Supports different requirement levels (required vs optional)

Usage:
    from backend.api.secrets_validator import validate_all_secrets, SecretsValidationError

    # At application startup:
    try:
        validation_result = validate_all_secrets()
        if not validation_result.is_valid:
            # Handle missing required secrets
            sys.exit(1)
    except SecretsValidationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
"""

import os
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class SecretLevel(Enum):
    """Defines the requirement level for a secret."""
    REQUIRED = "required"  # App cannot start without this
    RECOMMENDED = "recommended"  # App can start but functionality is limited
    OPTIONAL = "optional"  # Nice to have, no warning if missing


class SecretCategory(Enum):
    """Categories of secrets for better organization."""
    DATABASE = "database"
    AI_PROVIDER = "ai_provider"
    DATA_SOURCE = "data_source"
    AUTHENTICATION = "authentication"
    INTEGRATION = "integration"


@dataclass
class SecretConfig:
    """Configuration for a single secret."""
    name: str
    level: SecretLevel
    category: SecretCategory
    description: str
    validator: Optional[Callable[[str], bool]] = None
    min_length: int = 1
    pattern: Optional[str] = None  # Regex pattern for format validation
    masked_preview_length: int = 4  # How many chars to show in masked preview


@dataclass
class SecretValidationResult:
    """Result of validating a single secret."""
    name: str
    is_present: bool
    is_valid: bool
    level: SecretLevel
    category: SecretCategory
    error_message: Optional[str] = None
    masked_value: Optional[str] = None  # e.g., "sk-a****...****nxwQ"


@dataclass
class AllSecretsValidationResult:
    """Result of validating all secrets."""
    is_valid: bool  # True only if all REQUIRED secrets are valid
    results: list[SecretValidationResult] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)
    invalid_format: list[str] = field(default_factory=list)

    def get_summary(self) -> dict:
        """Get a summary suitable for logging (no sensitive data)."""
        return {
            "is_valid": self.is_valid,
            "total_checked": len(self.results),
            "missing_required": self.missing_required,
            "missing_recommended": self.missing_recommended,
            "invalid_format": self.invalid_format,
            "configured": [r.name for r in self.results if r.is_present and r.is_valid],
        }


class SecretsValidationError(Exception):
    """Raised when secrets validation fails critically."""

    def __init__(self, message: str, missing_secrets: list[str] = None):
        self.missing_secrets = missing_secrets or []
        super().__init__(message)


# =============================================================================
# Format Validators
# =============================================================================

def validate_anthropic_key(value: str) -> bool:
    """Validate Anthropic API key format (sk-ant-api...)."""
    return bool(re.match(r'^sk-ant-api[a-zA-Z0-9_-]{50,}$', value))


def validate_grok_key(value: str) -> bool:
    """Validate Grok/xAI API key format (xai-...)."""
    return bool(re.match(r'^xai-[a-zA-Z0-9_-]{40,}$', value))


def validate_supabase_url(value: str) -> bool:
    """Validate Supabase URL format (https://xxx.supabase.co)."""
    return bool(re.match(r'^https://[a-zA-Z0-9-]+\.supabase\.co$', value))


def validate_supabase_key(value: str) -> bool:
    """Validate Supabase service key format (JWT token)."""
    # Supabase keys are JWTs
    parts = value.split('.')
    return len(parts) == 3 and all(len(p) > 10 for p in parts)


def validate_odds_api_key(value: str) -> bool:
    """Validate The Odds API key format (32 char hex)."""
    return bool(re.match(r'^[a-f0-9]{32}$', value))


def validate_email(value: str) -> bool:
    """Validate email format."""
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value))


def validate_non_empty(value: str) -> bool:
    """Simple validator - just check non-empty."""
    return len(value.strip()) > 0


# =============================================================================
# Secret Definitions
# =============================================================================

SECRETS_CONFIG: list[SecretConfig] = [
    # Database (Required)
    SecretConfig(
        name="SUPABASE_URL",
        level=SecretLevel.REQUIRED,
        category=SecretCategory.DATABASE,
        description="Supabase project URL",
        validator=validate_supabase_url,
        min_length=30,
    ),
    SecretConfig(
        name="SUPABASE_SERVICE_KEY",
        level=SecretLevel.REQUIRED,
        category=SecretCategory.DATABASE,
        description="Supabase service role key (JWT)",
        validator=validate_supabase_key,
        min_length=100,
        masked_preview_length=10,
    ),

    # AI Providers (At least one recommended)
    SecretConfig(
        name="ANTHROPIC_API_KEY",
        level=SecretLevel.RECOMMENDED,
        category=SecretCategory.AI_PROVIDER,
        description="Claude API key for AI analysis",
        validator=validate_anthropic_key,
        min_length=50,
        pattern=r'^sk-ant-api',
    ),
    SecretConfig(
        name="GROK_API_KEY",
        level=SecretLevel.RECOMMENDED,
        category=SecretCategory.AI_PROVIDER,
        description="Grok/xAI API key for AI analysis",
        validator=validate_grok_key,
        min_length=40,
        pattern=r'^xai-',
    ),

    # Data Sources
    SecretConfig(
        name="ODDS_API_KEY",
        level=SecretLevel.RECOMMENDED,
        category=SecretCategory.DATA_SOURCE,
        description="The Odds API key for betting lines",
        validator=validate_odds_api_key,
        min_length=32,
    ),

    # KenPom (Optional - paid service)
    SecretConfig(
        name="KENPOM_EMAIL",
        level=SecretLevel.OPTIONAL,
        category=SecretCategory.DATA_SOURCE,
        description="KenPom account email",
        validator=validate_email,
        min_length=5,
    ),
    SecretConfig(
        name="KENPOM_PASSWORD",
        level=SecretLevel.OPTIONAL,
        category=SecretCategory.DATA_SOURCE,
        description="KenPom account password",
        validator=validate_non_empty,
        min_length=1,
    ),

    # API Authentication (Optional)
    SecretConfig(
        name="REFRESH_API_KEY",
        level=SecretLevel.OPTIONAL,
        category=SecretCategory.AUTHENTICATION,
        description="API key for refresh endpoint authentication",
        validator=validate_non_empty,
        min_length=16,
    ),

    # Kalshi Integration (Optional)
    SecretConfig(
        name="KALSHI_API_KEY",
        level=SecretLevel.OPTIONAL,
        category=SecretCategory.INTEGRATION,
        description="Kalshi prediction market API key",
        validator=validate_non_empty,
        min_length=10,
    ),
    SecretConfig(
        name="KALSHI_PRIVATE_KEY_PATH",
        level=SecretLevel.OPTIONAL,
        category=SecretCategory.INTEGRATION,
        description="Path to Kalshi RSA private key file",
        validator=validate_non_empty,
        min_length=1,
    ),
]


# =============================================================================
# Utility Functions
# =============================================================================

def mask_secret(value: str, preview_length: int = 4) -> str:
    """
    Mask a secret value for safe logging.

    SECURITY: Never log or expose full secret values.
    Shows only first and last few characters with asterisks in between.

    Examples:
        "sk-ant-api03-InC26..." -> "sk-a****...****nxwQ"
        "short" -> "s***t"
    """
    if not value:
        return "[empty]"

    length = len(value)
    if length <= preview_length * 2:
        # Very short - show first and last char only
        return f"{value[0]}{'*' * (length - 2)}{value[-1]}"

    return f"{value[:preview_length]}****...****{value[-preview_length:]}"


def validate_single_secret(config: SecretConfig) -> SecretValidationResult:
    """
    Validate a single secret against its configuration.

    SECURITY: Never includes the actual secret value in the result.
    """
    value = os.getenv(config.name)

    result = SecretValidationResult(
        name=config.name,
        is_present=False,
        is_valid=False,
        level=config.level,
        category=config.category,
    )

    # Check if present
    if not value:
        result.error_message = f"Environment variable {config.name} is not set"
        return result

    result.is_present = True
    result.masked_value = mask_secret(value, config.masked_preview_length)

    # Check minimum length
    if len(value) < config.min_length:
        result.error_message = f"{config.name} is too short (expected >= {config.min_length} chars)"
        return result

    # Check pattern if specified
    if config.pattern and not re.match(config.pattern, value):
        result.error_message = f"{config.name} does not match expected format"
        return result

    # Run custom validator if specified
    if config.validator:
        try:
            if not config.validator(value):
                result.error_message = f"{config.name} failed format validation"
                return result
        except Exception as e:
            # SECURITY: Don't expose validation error details
            logger.warning(f"Validator error for {config.name}: {type(e).__name__}")
            result.error_message = f"{config.name} validation failed"
            return result

    result.is_valid = True
    return result


def validate_all_secrets(
    raise_on_missing_required: bool = False
) -> AllSecretsValidationResult:
    """
    Validate all configured secrets.

    Args:
        raise_on_missing_required: If True, raises SecretsValidationError
            when required secrets are missing.

    Returns:
        AllSecretsValidationResult with validation status for all secrets.

    SECURITY:
        - Never logs actual secret values
        - Only logs masked previews and validation status
        - Safe to include result in logs or error messages
    """
    results = []
    missing_required = []
    missing_recommended = []
    invalid_format = []

    for config in SECRETS_CONFIG:
        result = validate_single_secret(config)
        results.append(result)

        if not result.is_present:
            if config.level == SecretLevel.REQUIRED:
                missing_required.append(config.name)
            elif config.level == SecretLevel.RECOMMENDED:
                missing_recommended.append(config.name)
        elif not result.is_valid:
            invalid_format.append(config.name)

    # Check if at least one AI provider is configured
    ai_providers = [r for r in results if r.category == SecretCategory.AI_PROVIDER]
    any_ai_configured = any(r.is_present and r.is_valid for r in ai_providers)

    if not any_ai_configured:
        logger.warning(
            "SECURITY: No AI provider configured (ANTHROPIC_API_KEY or GROK_API_KEY). "
            "AI analysis features will be unavailable."
        )

    # Determine overall validity (only REQUIRED secrets matter)
    is_valid = len(missing_required) == 0 and all(
        r.is_valid for r in results if r.level == SecretLevel.REQUIRED and r.is_present
    )

    validation_result = AllSecretsValidationResult(
        is_valid=is_valid,
        results=results,
        missing_required=missing_required,
        missing_recommended=missing_recommended,
        invalid_format=invalid_format,
    )

    if raise_on_missing_required and not is_valid:
        raise SecretsValidationError(
            f"Missing required secrets: {', '.join(missing_required)}",
            missing_secrets=missing_required,
        )

    return validation_result


def get_secrets_status() -> dict:
    """
    Get a safe-to-expose status of all secrets.

    Returns a dictionary suitable for health check endpoints.
    SECURITY: Only returns boolean configured status, never values.
    """
    status = {}

    for config in SECRETS_CONFIG:
        value = os.getenv(config.name)
        if value:
            result = validate_single_secret(config)
            status[config.name] = {
                "configured": True,
                "valid": result.is_valid,
                "level": config.level.value,
                "category": config.category.value,
            }
        else:
            status[config.name] = {
                "configured": False,
                "valid": False,
                "level": config.level.value,
                "category": config.category.value,
            }

    return status


def log_secrets_status():
    """
    Log the current secrets configuration status.

    SECURITY: Only logs configuration status, never actual values.
    Safe to call at application startup.
    """
    result = validate_all_secrets()
    summary = result.get_summary()

    if result.is_valid:
        logger.info(
            f"Secrets validation passed. "
            f"Configured: {len(summary['configured'])} secrets"
        )
    else:
        logger.error(
            f"Secrets validation FAILED. "
            f"Missing required: {summary['missing_required']}"
        )

    if summary['missing_recommended']:
        logger.warning(
            f"Recommended secrets not configured: {summary['missing_recommended']}. "
            f"Some features may be unavailable."
        )

    if summary['invalid_format']:
        logger.warning(
            f"Secrets with invalid format: {summary['invalid_format']}. "
            f"These may cause API errors."
        )


def check_ai_provider_available() -> tuple[bool, bool]:
    """
    Check if AI providers are available.

    Returns:
        Tuple of (claude_available, grok_available)
    """
    claude_key = os.getenv("ANTHROPIC_API_KEY")
    grok_key = os.getenv("GROK_API_KEY")

    claude_available = bool(claude_key and validate_anthropic_key(claude_key))
    grok_available = bool(grok_key and validate_grok_key(grok_key))

    return claude_available, grok_available


def require_secret(name: str) -> str:
    """
    Get a required secret or raise an error.

    Use this when a secret is absolutely required for a specific operation.

    SECURITY: Error message never includes the actual value.

    Raises:
        SecretsValidationError: If the secret is not configured or invalid.
    """
    config = next((c for c in SECRETS_CONFIG if c.name == name), None)

    if config is None:
        raise SecretsValidationError(f"Unknown secret: {name}")

    result = validate_single_secret(config)

    if not result.is_present:
        raise SecretsValidationError(
            f"Required secret {name} is not configured",
            missing_secrets=[name]
        )

    if not result.is_valid:
        raise SecretsValidationError(
            f"Secret {name} is configured but invalid: {result.error_message}",
            missing_secrets=[name]
        )

    return os.getenv(name)
