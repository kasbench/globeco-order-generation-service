"""
Validation Service interface.

This module defines the validation service interface for validating
business rules, data integrity, and optimization inputs.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List

from src.domain.entities.model import InvestmentModel


class ValidationService(ABC):
    """Interface for validation services."""

    @abstractmethod
    async def validate_model(self, model: InvestmentModel) -> bool:
        """
        Validate investment model business rules and constraints.

        Validates:
        - Name uniqueness and format
        - Position target sum ≤ 0.95
        - Maximum 100 positions with non-zero targets
        - Target percentage precision (multiples of 0.005)
        - Drift bounds validity
        - Portfolio ID format and existence

        Args:
            model: Investment model to validate

        Returns:
            True if model is valid

        Raises:
            ValidationError: If model data is invalid
            BusinessRuleViolationError: If model violates business rules
        """
        pass

    @abstractmethod
    async def validate_optimization_inputs(
        self,
        current_positions: Dict[str, int],
        prices: Dict[str, Decimal],
        market_value: Decimal,
        model: InvestmentModel,
    ) -> bool:
        """
        Validate inputs for portfolio optimization.

        Validates:
        - All positions have corresponding prices
        - All model securities have prices
        - Quantities are non-negative integers
        - Prices are positive
        - Market value is positive
        - Position values sum approximately to market value

        Args:
            current_positions: Current security quantities
            prices: Current market prices
            market_value: Total portfolio market value
            model: Investment model with targets

        Returns:
            True if inputs are valid

        Raises:
            ValidationError: If inputs are invalid
        """
        pass

    @abstractmethod
    async def validate_business_rules(self, model: InvestmentModel) -> bool:
        """
        Validate investment model business rules.

        Args:
            model: Investment model to validate

        Returns:
            True if all business rules are satisfied

        Raises:
            BusinessRuleViolationError: If business rules are violated
        """
        pass

    @abstractmethod
    async def validate_market_data(self, prices: Dict[str, Decimal]) -> bool:
        """
        Validate market data integrity.

        Validates:
        - All prices are positive
        - No missing or null prices
        - Price format and precision
        - Security ID format (24 alphanumeric characters)

        Args:
            prices: Market prices to validate

        Returns:
            True if market data is valid

        Raises:
            ValidationError: If market data is invalid
        """
        pass

    @abstractmethod
    async def validate_portfolio_data(
        self, positions: Dict[str, int], market_value: Decimal
    ) -> bool:
        """
        Validate portfolio position data.

        Validates:
        - All quantities are non-negative integers
        - Security IDs are properly formatted
        - Market value consistency

        Args:
            positions: Portfolio positions to validate
            market_value: Total portfolio market value

        Returns:
            True if portfolio data is valid

        Raises:
            ValidationError: If portfolio data is invalid
        """
        pass

    @abstractmethod
    async def validate_optimization_result(
        self,
        result_positions: Dict[str, int],
        model: InvestmentModel,
        prices: Dict[str, Decimal],
        market_value: Decimal,
    ) -> bool:
        """
        Validate optimization result against constraints.

        Validates:
        - All quantities are non-negative integers
        - Drift bounds are respected
        - Solution is mathematically valid
        - No constraint violations

        Args:
            result_positions: Optimized security quantities
            model: Investment model with constraints
            prices: Market prices used in optimization
            market_value: Total portfolio market value

        Returns:
            True if result is valid

        Raises:
            ValidationError: If result violates constraints
        """
        pass

    @abstractmethod
    async def validate_security_ids(self, security_ids: List[str]) -> bool:
        """
        Validate security ID format and uniqueness.

        Args:
            security_ids: List of security IDs to validate

        Returns:
            True if all security IDs are valid and unique

        Raises:
            ValidationError: If any security ID is invalid
        """
        pass

    @abstractmethod
    async def validate_percentage_precision(self, percentage: Decimal) -> bool:
        """
        Validate that percentage is a valid multiple of 0.005.

        Args:
            percentage: Percentage value to validate

        Returns:
            True if percentage precision is valid

        Raises:
            ValidationError: If percentage precision is invalid
        """
        pass
