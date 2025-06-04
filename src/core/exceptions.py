"""
Custom exceptions for the application.

This module defines custom exception classes for different types of errors
that can occur in the investment management system.
"""

from typing import Any, Dict, Optional


class ServiceException(Exception):
    """Base exception for all service-related errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "SERVICE_ERROR",
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(ServiceException):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class BusinessRuleViolationError(ServiceException):
    """Raised when business rules are violated."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="BUSINESS_RULE_VIOLATION",
            details=details,
        )


class ExternalServiceError(ServiceException):
    """Raised when external service calls fail."""

    def __init__(
        self,
        message: str,
        service: str = None,  # Accept both service and service_name for compatibility
        service_name: str = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        # Support both service and service_name parameters
        self.service_name = service or service_name or "unknown"
        self.status_code = status_code

        error_details = {"service_name": self.service_name}
        if status_code:
            error_details["status_code"] = status_code
        if details:
            error_details.update(details)

        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=error_details,
        )


class OptimizationError(ServiceException):
    """Raised when portfolio optimization fails."""

    def __init__(
        self,
        message: str,
        solver_status: str | None = None,
        solve_time: float | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.solver_status = solver_status
        self.solve_time = solve_time

        error_details = {}
        if solver_status:
            error_details["solver_status"] = solver_status
        if solve_time is not None:
            error_details["solve_time"] = solve_time
        if details:
            error_details.update(details)

        super().__init__(
            message=message,
            error_code="OPTIMIZATION_ERROR",
            details=error_details,
        )


class RepositoryError(ServiceException):
    """Raised when repository operations fail."""

    def __init__(
        self,
        message: str,
        operation: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.operation = operation
        self.entity_type = entity_type
        self.entity_id = entity_id

        error_details = {"operation": operation}
        if entity_type:
            error_details["entity_type"] = entity_type
        if entity_id:
            error_details["entity_id"] = entity_id
        if details:
            error_details.update(details)

        super().__init__(
            message=message,
            error_code="REPOSITORY_ERROR",
            details=error_details,
        )


class InfeasibleSolutionError(OptimizationError):
    """Raised when optimization problem has no feasible solution."""

    def __init__(
        self,
        message: str = "No feasible solution exists for the optimization problem",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            solver_status="INFEASIBLE",
            details=details,
        )
        self.error_code = "INFEASIBLE_SOLUTION"


class SolverTimeoutError(OptimizationError):
    """Raised when optimization solver exceeds time limit."""

    def __init__(
        self,
        message: str = "Optimization solver exceeded time limit",
        timeout_seconds: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if timeout_seconds:
            error_details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            solver_status="TIMEOUT",
            details=error_details,
        )
        self.error_code = "SOLVER_TIMEOUT"


class ConcurrencyError(RepositoryError):
    """Raised when concurrent modification conflicts occur."""

    def __init__(
        self,
        message: str = "Concurrent modification detected",
        expected_version: int | None = None,
        actual_version: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if expected_version is not None:
            error_details["expected_version"] = expected_version
        if actual_version is not None:
            error_details["actual_version"] = actual_version

        super().__init__(
            message=message,
            operation="update",
            details=error_details,
        )
        self.error_code = "CONCURRENCY_ERROR"


# Alias for backward compatibility
OptimisticLockingError = ConcurrencyError


class NotFoundError(RepositoryError):
    """Raised when requested entity is not found."""

    def __init__(
        self,
        message: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            operation="get",
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        self.error_code = "NOT_FOUND"


class ConfigurationError(ServiceException):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key

        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=error_details,
        )


class OrderGenerationServiceError(Exception):
    """Base exception for all Order Generation Service errors."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.details = details or {}


class ModelNotFoundError(OrderGenerationServiceError):
    """Raised when a requested investment model is not found."""

    def __init__(self, model_id: str, **kwargs):
        message = f"Investment model not found: {model_id}"
        super().__init__(message, "MODEL_NOT_FOUND", **kwargs)
        self.details["model_id"] = model_id


class PortfolioNotFoundError(OrderGenerationServiceError):
    """Raised when a requested portfolio is not found."""

    def __init__(self, portfolio_id: str, **kwargs):
        message = f"Portfolio not found: {portfolio_id}"
        super().__init__(message, "PORTFOLIO_NOT_FOUND", **kwargs)
        self.details["portfolio_id"] = portfolio_id


class PortfolioAccountingServiceError(ExternalServiceError):
    """Raised when Portfolio Accounting Service calls fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, "Portfolio Accounting Service", **kwargs)


class PricingServiceError(ExternalServiceError):
    """Raised when Pricing Service calls fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, "Pricing Service", **kwargs)


class PortfolioServiceError(ExternalServiceError):
    """Raised when Portfolio Service calls fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, "Portfolio Service", **kwargs)


class SecurityServiceError(ExternalServiceError):
    """Raised when Security Service calls fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, "Security Service", **kwargs)


class DatabaseError(OrderGenerationServiceError):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        collection: str | None = None,
        **kwargs,
    ):
        super().__init__(message, "DATABASE_ERROR", **kwargs)
        if operation:
            self.details["operation"] = operation
        if collection:
            self.details["collection"] = collection


class AuthenticationError(OrderGenerationServiceError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, "AUTHENTICATION_ERROR", **kwargs)


class AuthorizationError(OrderGenerationServiceError):
    """Raised when authorization fails."""

    def __init__(
        self,
        message: str = "Access denied",
        required_permission: str | None = None,
        **kwargs,
    ):
        super().__init__(message, "AUTHORIZATION_ERROR", **kwargs)
        if required_permission:
            self.details["required_permission"] = required_permission


class RateLimitExceededError(OrderGenerationServiceError):
    """Raised when rate limits are exceeded."""

    def __init__(
        self,
        message: str,
        limit: int,
        window_seconds: int,
        retry_after_seconds: int | None = None,
        **kwargs,
    ):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", **kwargs)
        self.details.update(
            {
                "limit": limit,
                "window_seconds": window_seconds,
            }
        )
        if retry_after_seconds:
            self.details["retry_after_seconds"] = retry_after_seconds


class MathematicalError(OrderGenerationServiceError):
    """Raised when mathematical calculations fail."""

    def __init__(self, message: str, calculation_type: str | None = None, **kwargs):
        super().__init__(message, "MATHEMATICAL_ERROR", **kwargs)
        if calculation_type:
            self.details["calculation_type"] = calculation_type


class TargetSumExceededError(BusinessRuleViolationError):
    """Raised when position targets sum exceeds 95%."""

    def __init__(self, actual_sum: float, **kwargs):
        message = (
            f"Position targets sum ({actual_sum:.1%}) exceeds maximum allowed (95%)"
        )
        super().__init__(message, rule="target_sum_limit", **kwargs)
        self.details["actual_sum"] = actual_sum
        self.details["maximum_allowed"] = 0.95


class InvalidTargetPrecisionError(BusinessRuleViolationError):
    """Raised when target precision is not a multiple of 0.005."""

    def __init__(self, target: float, **kwargs):
        message = f"Target {target:.3f} is not a multiple of 0.005"
        super().__init__(message, rule="target_precision", **kwargs)
        self.details["target"] = target
        self.details["required_precision"] = 0.005


class TooManyPositionsError(BusinessRuleViolationError):
    """Raised when model has too many positions."""

    def __init__(self, position_count: int, **kwargs):
        message = f"Model has {position_count} positions, maximum allowed is 100"
        super().__init__(message, rule="position_limit", **kwargs)
        self.details["position_count"] = position_count
        self.details["maximum_allowed"] = 100


class DuplicateSecurityError(BusinessRuleViolationError):
    """Raised when duplicate securities are found in a model."""

    def __init__(self, security_id: str, **kwargs):
        message = f"Duplicate security found in model: {security_id}"
        super().__init__(message, rule="security_uniqueness", **kwargs)
        self.details["security_id"] = security_id


class InvalidDriftBoundsError(BusinessRuleViolationError):
    """Raised when drift bounds are invalid."""

    def __init__(
        self,
        low_drift: float,
        high_drift: float,
        security_id: str | None = None,
        **kwargs,
    ):
        message = f"Invalid drift bounds: low={low_drift}, high={high_drift}"
        super().__init__(message, rule="drift_bounds", **kwargs)
        self.details.update(
            {
                "low_drift": low_drift,
                "high_drift": high_drift,
            }
        )
        if security_id:
            self.details["security_id"] = security_id


class DatabaseConnectionError(ServiceException):
    """Exception raised when database connection fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_CONNECTION_ERROR",
            details=details or {},
        )


class ServiceTimeoutError(ExternalServiceError):
    """Raised when external service requests timeout."""

    def __init__(
        self,
        message: str,
        service: str = None,
        timeout_seconds: float | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if timeout_seconds:
            error_details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            service=service,
            details=error_details,
        )
        self.error_code = "SERVICE_TIMEOUT"


class ServiceUnavailableError(ExternalServiceError):
    """Raised when external service is unavailable (circuit breaker open)."""

    def __init__(
        self,
        message: str,
        service: str = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            service=service,
            status_code=503,
            details=details,
        )
        self.error_code = "SERVICE_UNAVAILABLE"
