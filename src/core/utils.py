"""
Core utility functions for the Order Generation Service.

This module provides common utility functions including structured logging,
correlation ID management, and other cross-cutting concerns.
"""

import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

# Context variable for correlation ID
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """
    Get the current correlation ID, generating one if none exists.

    Returns:
        Current correlation ID
    """
    correlation_id = correlation_id_var.get()
    if correlation_id is None:
        correlation_id = generate_correlation_id()
        correlation_id_var.set(correlation_id)
    return correlation_id


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID.

    Returns:
        New UUID-based correlation ID
    """
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current context.

    Args:
        correlation_id: The correlation ID to set
    """
    correlation_id_var.set(correlation_id)


def configure_structured_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging with correlation IDs.

    Args:
        log_level: Logging level to configure
    """
    print(f"[UTILS] Configuring structured logging with level: {log_level}")

    # Check current root logger level before configuration
    root_logger = logging.getLogger()
    print(
        f"[UTILS] Root logger level before: {logging.getLevelName(root_logger.level)}"
    )

    def add_correlation_id(logger, method_name, event_dict):
        """Add correlation ID to log events."""
        event_dict["correlation_id"] = get_correlation_id()
        return event_dict

    def add_timestamp(logger, method_name, event_dict):
        """Add timestamp to log events."""
        event_dict["timestamp"] = datetime.utcnow().isoformat()
        return event_dict

    def add_service_info(logger, method_name, event_dict):
        """Add service information to log events."""
        event_dict["service"] = "order-generation-service"
        event_dict["version"] = "0.1.0"
        return event_dict

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            add_correlation_id,
            add_timestamp,
            add_service_info,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging only if not already configured
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        print(
            f"[UTILS] No handlers found, calling basicConfig with level {log_level.upper()}"
        )
        logging.basicConfig(
            format="%(message)s",
            level=getattr(logging, log_level.upper()),
            stream=None,
        )
    else:
        print(
            f"[UTILS] Handlers found ({len(root_logger.handlers)}), setting level to {log_level.upper()}"
        )
        # Update existing logger level to match the requested level
        root_logger.setLevel(getattr(logging, log_level.upper()))

    # Check final level
    final_level = logging.getLevelName(root_logger.level)
    print(f"[UTILS] Root logger level after configuration: {final_level}")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structured logger
    """
    return structlog.get_logger(name)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def safe_decimal_conversion(value: str | int | float | Decimal) -> Decimal:
    """
    Safely convert a value to Decimal with proper error handling.

    Args:
        value: Value to convert to Decimal

    Returns:
        Decimal representation of the value

    Raises:
        ValueError: If conversion fails
    """
    try:
        if isinstance(value, Decimal):
            return value
        elif isinstance(value, (int, float)):
            return Decimal(str(value))
        elif isinstance(value, str):
            return Decimal(value)
        else:
            raise ValueError(f"Cannot convert {type(value)} to Decimal")
    except Exception as e:
        raise ValueError(f"Error converting {value} to Decimal: {e}")


def round_decimal(value: Decimal, places: int = 4) -> Decimal:
    """
    Round a decimal to specified number of places.

    Args:
        value: Decimal value to round
        places: Number of decimal places

    Returns:
        Rounded decimal value
    """
    quantize_value = Decimal("0.1") ** places
    return value.quantize(quantize_value)


def calculate_percentage(part: Decimal, whole: Decimal) -> Decimal:
    """
    Calculate percentage with proper error handling.

    Args:
        part: Part value
        whole: Whole value

    Returns:
        Percentage as decimal (0.0 to 1.0)

    Raises:
        ValueError: If whole is zero
    """
    if whole == 0:
        raise ValueError("Cannot calculate percentage with zero denominator")

    return round_decimal(part / whole, 6)


def validate_security_id(security_id: str) -> bool:
    """
    Validate that a security ID has the correct format.

    Args:
        security_id: Security ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(security_id, str):
        return False

    if len(security_id) != 24:
        return False

    # Check if it's a valid hex string
    try:
        int(security_id, 16)
        return True
    except ValueError:
        return False


def validate_portfolio_id(portfolio_id: str) -> bool:
    """
    Validate that a portfolio ID has the correct format.

    Args:
        portfolio_id: Portfolio ID to validate

    Returns:
        True if valid, False otherwise
    """
    # Same format as security ID for now
    return validate_security_id(portfolio_id)


def format_currency(amount: Decimal, currency: str = "USD") -> str:
    """
    Format a decimal amount as currency.

    Args:
        amount: Amount to format
        currency: Currency code

    Returns:
        Formatted currency string
    """
    if currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def truncate_string(text: str, max_length: int = 50) -> str:
    """
    Truncate a string to maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def deep_merge_dicts(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)

    Returns:
        Merged dictionary
    """
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def sanitize_for_logging(data: Any, max_depth: int = 3) -> Any:
    """
    Sanitize data for safe logging (remove sensitive information).

    Args:
        data: Data to sanitize
        max_depth: Maximum recursion depth

    Returns:
        Sanitized data safe for logging
    """
    if max_depth <= 0:
        return "..."

    sensitive_keys = {
        "password",
        "secret",
        "key",
        "token",
        "auth",
        "credential",
        "private",
        "confidential",
        "ssn",
        "account",
    }

    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if any(sensitive_word in key.lower() for sensitive_word in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = sanitize_for_logging(value, max_depth - 1)
        return sanitized
    elif isinstance(data, list):
        return [
            sanitize_for_logging(item, max_depth - 1) for item in data[:10]
        ]  # Limit list size
    elif isinstance(data, str) and len(data) > 200:
        return truncate_string(data, 200)
    else:
        return data


def create_response_metadata() -> dict[str, Any]:
    """
    Create standard response metadata.

    Returns:
        Dictionary containing response metadata
    """
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "correlation_id": get_correlation_id(),
        "service": "order-generation-service",
        "version": "0.1.0",
    }
