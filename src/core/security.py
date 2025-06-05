"""
Security utilities for the Order Generation Service.

This module provides security-related functions including authentication,
authorization, input validation, and security utilities.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import get_settings
from src.core.utils import get_logger

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time

    Returns:
        JWT token string
    """
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt


def verify_token(token: str) -> dict[str, Any] | None:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token data or None if invalid
    """
    settings = get_settings()

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except JWTError as e:
        logger.warning("JWT verification failed", error=str(e))
        return None


def generate_api_key() -> str:
    """
    Generate a secure API key.

    Returns:
        Random API key string
    """
    return secrets.token_urlsafe(32)


def validate_api_key(api_key: str, valid_keys: list[str]) -> bool:
    """
    Validate an API key against a list of valid keys.

    Args:
        api_key: API key to validate
        valid_keys: List of valid API keys

    Returns:
        True if API key is valid, False otherwise
    """
    # Use constant-time comparison to prevent timing attacks
    for valid_key in valid_keys:
        if hmac.compare_digest(api_key, valid_key):
            return True
    return False


def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injection attacks.

    Args:
        input_string: Input string to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(input_string, str):
        return ""

    # Truncate to max length
    sanitized = input_string[:max_length]

    # Remove potentially dangerous characters
    dangerous_chars = ["<", ">", '"', "'", "&", "\x00", "\n", "\r", "\t"]
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")

    return sanitized.strip()


def validate_financial_amount(amount: Any) -> bool:
    """
    Validate that an amount is a valid financial value.

    Args:
        amount: Amount to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        from decimal import Decimal

        # Convert to Decimal for validation
        decimal_amount = Decimal(str(amount))

        # Check for reasonable bounds
        if decimal_amount < 0:
            return False

        # Check for reasonable maximum (1 trillion)
        if decimal_amount > Decimal("1000000000000"):
            return False

        # Check decimal places (max 4)
        if decimal_amount.as_tuple().exponent < -4:
            return False

        return True
    except Exception:
        return False


def validate_percentage(percentage: Any) -> bool:
    """
    Validate that a value is a valid percentage (0-1).

    Args:
        percentage: Percentage to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        from decimal import Decimal

        decimal_percentage = Decimal(str(percentage))
        return Decimal("0") <= decimal_percentage <= Decimal("1")
    except Exception:
        return False


def calculate_request_signature(
    method: str, url: str, body: str, timestamp: str, secret: str
) -> str:
    """
    Calculate HMAC signature for request authentication.

    Args:
        method: HTTP method
        url: Request URL
        body: Request body
        timestamp: Request timestamp
        secret: Secret key

    Returns:
        HMAC signature
    """
    # Create string to sign
    string_to_sign = f"{method}\n{url}\n{body}\n{timestamp}"

    # Calculate HMAC
    signature = hmac.new(
        secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return signature


def verify_request_signature(
    method: str,
    url: str,
    body: str,
    timestamp: str,
    signature: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Verify request signature and timestamp.

    Args:
        method: HTTP method
        url: Request URL
        body: Request body
        timestamp: Request timestamp
        signature: Provided signature
        secret: Secret key
        tolerance_seconds: Maximum age of request in seconds

    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Check timestamp (prevent replay attacks)
        request_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        current_time = datetime.utcnow().replace(tzinfo=request_time.tzinfo)

        if abs((current_time - request_time).total_seconds()) > tolerance_seconds:
            logger.warning("Request timestamp too old", timestamp=timestamp)
            return False

        # Calculate expected signature
        expected_signature = calculate_request_signature(
            method, url, body, timestamp, secret
        )

        # Compare signatures using constant-time comparison
        return hmac.compare_digest(signature, expected_signature)

    except Exception as e:
        logger.warning("Signature verification failed", error=str(e))
        return False


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging (e.g., API keys, account numbers).

    Args:
        data: Sensitive data to mask
        visible_chars: Number of characters to leave visible

    Returns:
        Masked string
    """
    if len(data) <= visible_chars:
        return "*" * len(data)

    return data[:visible_chars] + "*" * (len(data) - visible_chars)


def generate_secure_filename(original_filename: str) -> str:
    """
    Generate a secure filename to prevent directory traversal attacks.

    Args:
        original_filename: Original filename

    Returns:
        Secure filename
    """
    import os
    import re

    # Remove directory separators and other dangerous characters
    filename = os.path.basename(original_filename)
    filename = re.sub(r"[^a-zA-Z0-9._-]", "", filename)

    # Ensure filename is not empty
    if not filename:
        filename = "file"

    # Add timestamp to ensure uniqueness
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(filename)

    return f"{name}_{timestamp}{ext}"


def rate_limit_key(identifier: str, action: str) -> str:
    """
    Generate a rate limiting key.

    Args:
        identifier: User/IP identifier
        action: Action being rate limited

    Returns:
        Rate limiting key
    """
    return f"rate_limit:{action}:{hashlib.sha256(identifier.encode()).hexdigest()[:16]}"


class SecurityHeaders:
    """Security headers for HTTP responses."""

    @staticmethod
    def get_default_headers() -> dict[str, str]:
        """
        Get default security headers.

        Returns:
            Dictionary of security headers
        """
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
        }


def validate_input_constraints(
    value: Any,
    min_length: int | None = None,
    max_length: int | None = None,
    pattern: str | None = None,
    allowed_values: list[Any] | None = None,
) -> bool:
    """
    Validate input against various constraints.

    Args:
        value: Value to validate
        min_length: Minimum length
        max_length: Maximum length
        pattern: Regex pattern to match
        allowed_values: List of allowed values

    Returns:
        True if valid, False otherwise
    """
    try:
        # Convert to string for length checks
        str_value = str(value)

        # Check length constraints
        if min_length is not None and len(str_value) < min_length:
            return False

        if max_length is not None and len(str_value) > max_length:
            return False

        # Check pattern
        if pattern is not None:
            import re

            if not re.match(pattern, str_value):
                return False

        # Check allowed values
        if allowed_values is not None and value not in allowed_values:
            return False

        return True

    except Exception:
        return False
