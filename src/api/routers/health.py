"""
Health check endpoints for Kubernetes liveness and readiness probes.

This module provides health check endpoints that can be used by Kubernetes
to determine if the service is alive and ready to serve traffic.
"""

from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.config import get_settings, Settings
from src.core.utils import get_logger, get_correlation_id


logger = get_logger(__name__)
router = APIRouter()


class HealthStatus(BaseModel):
    """Health status response model."""

    status: str  # "healthy" or "unhealthy"
    timestamp: datetime
    service: str
    version: str
    correlation_id: str
    checks: Dict[str, Any]
    uptime_seconds: Optional[float] = None


class HealthCheck:
    """Health check implementation."""

    def __init__(self):
        self.start_time = datetime.utcnow()

    async def check_database(self) -> Dict[str, Any]:
        """
        Check database connectivity.

        Returns:
            Dictionary with database health status
        """
        try:
            # TODO: Implement actual database connectivity check
            # For now, return healthy status
            return {
                "status": "healthy",
                "message": "Database connection successful",
                "response_time_ms": 5.0,
            }
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "message": f"Database connection failed: {e}",
                "response_time_ms": None,
            }

    async def check_external_services(self) -> Dict[str, Any]:
        """
        Check external service connectivity.

        Returns:
            Dictionary with external services health status
        """
        services = {
            "portfolio_accounting": "Portfolio Accounting Service",
            "pricing": "Pricing Service",
            "portfolio": "Portfolio Service",
            "security": "Security Service",
        }

        service_status = {}

        for service_key, service_name in services.items():
            try:
                # TODO: Implement actual service connectivity checks
                # For now, return healthy status
                service_status[service_key] = {
                    "status": "healthy",
                    "message": f"{service_name} reachable",
                    "response_time_ms": 10.0,
                }
            except Exception as e:
                logger.warning(f"{service_name} health check failed", error=str(e))
                service_status[service_key] = {
                    "status": "unhealthy",
                    "message": f"{service_name} unreachable: {e}",
                    "response_time_ms": None,
                }

        # Overall status is healthy if all services are healthy
        all_healthy = all(
            status["status"] == "healthy" for status in service_status.values()
        )

        return {
            "status": "healthy" if all_healthy else "degraded",
            "services": service_status,
        }

    async def check_optimization_engine(self) -> Dict[str, Any]:
        """
        Check optimization engine availability.

        Returns:
            Dictionary with optimization engine health status
        """
        try:
            # TODO: Implement actual CVXPY solver check
            # For now, return healthy status
            import cvxpy as cp

            # Simple test problem to verify CVXPY is working
            x = cp.Variable()
            problem = cp.Problem(cp.Minimize(cp.square(x - 1)))
            problem.solve(verbose=False)

            if problem.status == "optimal":
                return {
                    "status": "healthy",
                    "message": "Optimization engine operational",
                    "solver_status": problem.status,
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": "Optimization engine test failed",
                    "solver_status": problem.status,
                }
        except Exception as e:
            logger.error("Optimization engine health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "message": f"Optimization engine error: {e}",
                "solver_status": None,
            }

    async def get_health_status(
        self, include_external: bool = True, include_optimization: bool = True
    ) -> HealthStatus:
        """
        Get overall health status.

        Args:
            include_external: Whether to check external services
            include_optimization: Whether to check optimization engine

        Returns:
            Complete health status
        """
        settings = get_settings()
        checks = {}

        # Always check database
        checks["database"] = await self.check_database()

        # Optionally check external services
        if include_external:
            checks["external_services"] = await self.check_external_services()

        # Optionally check optimization engine
        if include_optimization:
            checks["optimization_engine"] = await self.check_optimization_engine()

        # Determine overall status
        all_checks_healthy = all(
            check["status"] == "healthy"
            for check in checks.values()
            if isinstance(check, dict) and "status" in check
        )

        # Handle degraded external services
        external_degraded = (
            "external_services" in checks
            and checks["external_services"]["status"] == "degraded"
        )

        if all_checks_healthy:
            overall_status = "healthy"
        elif external_degraded and checks["database"]["status"] == "healthy":
            # Service can still operate with degraded external services
            overall_status = "healthy"
        else:
            overall_status = "unhealthy"

        # Calculate uptime
        uptime = (datetime.utcnow() - self.start_time).total_seconds()

        return HealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow(),
            service=settings.service_name,
            version=settings.version,
            correlation_id=get_correlation_id(),
            checks=checks,
            uptime_seconds=uptime,
        )


# Global health check instance
health_check = HealthCheck()


@router.get("/live", response_model=HealthStatus, tags=["health"])
async def liveness_probe(settings: Settings = Depends(get_settings)) -> HealthStatus:
    """
    Kubernetes liveness probe endpoint.

    This endpoint performs basic health checks to determine if the service
    is alive and should not be restarted. It only checks essential components
    and avoids external dependencies that might cause false failures.

    Returns:
        Health status focused on service liveness
    """
    logger.debug("Liveness probe requested")

    try:
        # For liveness probe, only check critical internal components
        health_status = await health_check.get_health_status(
            include_external=False,  # Don't check external services for liveness
            include_optimization=True,  # Check optimization engine
        )

        if health_status.status == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service is not alive",
            )

        return health_status

    except Exception as e:
        logger.error("Liveness probe failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Liveness check failed: {e}",
        )


@router.get("/ready", response_model=HealthStatus, tags=["health"])
async def readiness_probe(settings: Settings = Depends(get_settings)) -> HealthStatus:
    """
    Kubernetes readiness probe endpoint.

    This endpoint performs comprehensive health checks to determine if the
    service is ready to serve traffic. It checks all dependencies including
    external services.

    Returns:
        Health status focused on service readiness
    """
    logger.debug("Readiness probe requested")

    try:
        # For readiness probe, check all dependencies
        health_status = await health_check.get_health_status(
            include_external=True,  # Check external services
            include_optimization=True,  # Check optimization engine
        )

        if health_status.status == "unhealthy":
            # Allow degraded external services for readiness
            external_degraded = (
                "external_services" in health_status.checks
                and health_status.checks["external_services"]["status"] == "degraded"
            )
            database_healthy = (
                "database" in health_status.checks
                and health_status.checks["database"]["status"] == "healthy"
            )

            if not (external_degraded and database_healthy):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service is not ready",
                )

        return health_status

    except Exception as e:
        logger.error("Readiness probe failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Readiness check failed: {e}",
        )


@router.get("/health", response_model=HealthStatus, tags=["health"])
async def health_check_endpoint(
    include_external: bool = True,
    include_optimization: bool = True,
    settings: Settings = Depends(get_settings),
) -> HealthStatus:
    """
    Comprehensive health check endpoint.

    This endpoint provides detailed health information about all service
    components and dependencies. It can be used for monitoring and debugging.

    Args:
        include_external: Whether to check external services
        include_optimization: Whether to check optimization engine

    Returns:
        Detailed health status
    """
    logger.info(
        "Health check requested",
        include_external=include_external,
        include_optimization=include_optimization,
    )

    return await health_check.get_health_status(
        include_external=include_external,
        include_optimization=include_optimization,
    )
