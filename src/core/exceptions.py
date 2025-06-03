"""
Custom exceptions for the Order Generation Service.

This module defines custom exception classes for handling various error
scenarios in a structured and consistent way throughout the application.
"""

from typing import Any, Dict, Optional


class OrderGenerationServiceError(Exception):
    """Base exception for all Order Generation Service errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.details = details or {}


class ValidationError(OrderGenerationServiceError):
    """Raised when input validation fails."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(message, "VALIDATION_ERROR", **kwargs)
        if field:
            self.details["field"] = field
        if value is not None:
            self.details["value"] = str(value)


class BusinessRuleViolationError(OrderGenerationServiceError):
    """Raised when business rules are violated."""
    
    def __init__(
        self,
        message: str,
        rule: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, "BUSINESS_RULE_VIOLATION", **kwargs)
        if rule:
            self.details["rule"] = rule


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


class OptimizationError(OrderGenerationServiceError):
    """Raised when portfolio optimization fails."""
    
    def __init__(
        self,
        message: str,
        solver_status: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, "OPTIMIZATION_ERROR", **kwargs)
        if solver_status:
            self.details["solver_status"] = solver_status
        if portfolio_id:
            self.details["portfolio_id"] = portfolio_id


class InfeasibleSolutionError(OptimizationError):
    """Raised when optimization problem has no feasible solution."""
    
    def __init__(self, portfolio_id: Optional[str] = None, **kwargs):
        message = "No feasible solution exists for the given constraints"
        super().__init__(
            message,
            solver_status="INFEASIBLE",
            portfolio_id=portfolio_id,
            error_code="INFEASIBLE_SOLUTION",
            **kwargs
        )


class SolverTimeoutError(OptimizationError):
    """Raised when optimization solver exceeds timeout."""
    
    def __init__(
        self,
        timeout_seconds: int,
        portfolio_id: Optional[str] = None,
        **kwargs
    ):
        message = f"Optimization solver exceeded {timeout_seconds} second timeout"
        super().__init__(
            message,
            solver_status="TIMEOUT",
            portfolio_id=portfolio_id,
            error_code="SOLVER_TIMEOUT",
            **kwargs
        )
        self.details["timeout_seconds"] = timeout_seconds


class ExternalServiceError(OrderGenerationServiceError):
    """Raised when external service calls fail."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        status_code: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", **kwargs)
        self.details["service_name"] = service_name
        if status_code:
            self.details["status_code"] = status_code


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


class ConcurrencyError(OrderGenerationServiceError):
    """Raised when concurrent modification conflicts occur."""
    
    def __init__(
        self,
        message: str,
        resource_type: str,
        resource_id: str,
        expected_version: Optional[int] = None,
        actual_version: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, "CONCURRENCY_ERROR", **kwargs)
        self.details.update({
            "resource_type": resource_type,
            "resource_id": resource_id,
        })
        if expected_version is not None:
            self.details["expected_version"] = expected_version
        if actual_version is not None:
            self.details["actual_version"] = actual_version


class DatabaseError(OrderGenerationServiceError):
    """Raised when database operations fail."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        collection: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, "DATABASE_ERROR", **kwargs)
        if operation:
            self.details["operation"] = operation
        if collection:
            self.details["collection"] = collection


class ConfigurationError(OrderGenerationServiceError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(
        self,
        message: str,
        setting_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, "CONFIGURATION_ERROR", **kwargs)
        if setting_name:
            self.details["setting_name"] = setting_name


class AuthenticationError(OrderGenerationServiceError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, "AUTHENTICATION_ERROR", **kwargs)


class AuthorizationError(OrderGenerationServiceError):
    """Raised when authorization fails."""
    
    def __init__(
        self,
        message: str = "Access denied",
        required_permission: Optional[str] = None,
        **kwargs
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
        retry_after_seconds: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", **kwargs)
        self.details.update({
            "limit": limit,
            "window_seconds": window_seconds,
        })
        if retry_after_seconds:
            self.details["retry_after_seconds"] = retry_after_seconds


class MathematicalError(OrderGenerationServiceError):
    """Raised when mathematical calculations fail."""
    
    def __init__(
        self,
        message: str,
        calculation_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, "MATHEMATICAL_ERROR", **kwargs)
        if calculation_type:
            self.details["calculation_type"] = calculation_type


class TargetSumExceededError(BusinessRuleViolationError):
    """Raised when position targets sum exceeds 95%."""
    
    def __init__(self, actual_sum: float, **kwargs):
        message = f"Position targets sum ({actual_sum:.1%}) exceeds maximum allowed (95%)"
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
        security_id: Optional[str] = None,
        **kwargs
    ):
        message = f"Invalid drift bounds: low={low_drift}, high={high_drift}"
        super().__init__(message, rule="drift_bounds", **kwargs)
        self.details.update({
            "low_drift": low_drift,
            "high_drift": high_drift,
        })
        if security_id:
            self.details["security_id"] = security_id 