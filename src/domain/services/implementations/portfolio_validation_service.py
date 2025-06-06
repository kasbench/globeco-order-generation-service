"""
Portfolio Validation Service implementation.

This module contains the concrete implementation of the ValidationService interface,
providing comprehensive business rule validation and input validation for investment models.
"""

import re
from decimal import Decimal

from src.core.exceptions import BusinessRuleViolationError, ValidationError
from src.domain.entities.model import InvestmentModel
from src.domain.services.validation_service import ValidationService


class PortfolioValidationService(ValidationService):
    """Concrete implementation of portfolio validation service."""

    async def validate_model(self, model: InvestmentModel) -> bool:
        """
        Validate investment model business rules and constraints.

        Args:
            model: Investment model to validate

        Returns:
            True if model is valid

        Raises:
            ValidationError: If model data is invalid
            BusinessRuleViolationError: If model violates business rules
        """
        # Basic model validation
        await self._validate_model_basic_fields(model)

        # Business rule validation
        await self.validate_business_rules(model)

        return True

    async def validate_optimization_inputs(
        self,
        current_positions: dict[str, int],
        prices: dict[str, Decimal],
        market_value: Decimal,
        model: InvestmentModel,
    ) -> bool:
        """
        Validate inputs for portfolio optimization.

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
        # Validate market value
        if market_value <= 0:
            raise ValidationError("Market value must be positive")

        # Validate portfolio data
        await self.validate_portfolio_data(current_positions, market_value)

        # Validate market data
        await self.validate_market_data(prices)

        # Validate that all model securities have prices
        for position in model.positions:
            if position.security_id not in prices:
                raise ValidationError(
                    f"Missing price for security {position.security_id} required by model"
                )

        # # Validate position values approximately match market value
        # total_position_value = Decimal("0")
        # for security_id, quantity in current_positions.items():
        #     if security_id in prices:
        #         total_position_value += Decimal(str(quantity)) * prices[security_id]

        # # Allow up to 10% discrepancy for cash allocation
        # min_expected = market_value * Decimal("0.85")  # 85% minimum
        # max_expected = market_value * Decimal("1.05")  # 105% maximum (includes cash)

        # if not (min_expected <= total_position_value <= max_expected):
        #     raise ValidationError(
        #         f"Position values ({total_position_value}) do not approximately match "
        #         f"market value ({market_value})"
        #     )

        return True

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
        # Rule 1: Target sum ≤ 0.95 (95% maximum, 5% minimum cash)
        await self._validate_target_sum_limit(model)

        # Rule 2: Maximum 100 positions with non-zero targets
        await self._validate_position_count_limit(model)

        # Rule 3: Target precision (multiples of 0.005)
        await self._validate_target_precision(model)

        # Rule 4: Security uniqueness within model
        await self._validate_security_uniqueness(model)

        # Rule 5: Drift bounds validity
        await self._validate_drift_bounds(model)

        # Rule 6: Portfolio associations
        await self._validate_portfolio_associations(model)

        return True

    async def validate_market_data(self, prices: dict[str, Decimal]) -> bool:
        """
        Validate market data integrity.

        Args:
            prices: Market prices to validate

        Returns:
            True if market data is valid

        Raises:
            ValidationError: If market data is invalid
        """
        if not prices:
            raise ValidationError("Market data cannot be empty")

        for security_id, price in prices.items():
            # Validate security ID format
            if not self._is_valid_security_id(security_id):
                raise ValidationError(f"Invalid security ID format: {security_id}")

            # Validate price type
            if not isinstance(price, Decimal):
                raise ValidationError(f"Price for {security_id} must be a Decimal")

            # Validate price value
            if price <= 0:
                raise ValidationError(f"Price for {security_id} must be positive")

        return True

    async def validate_portfolio_data(
        self, positions: dict[str, int], market_value: Decimal
    ) -> bool:
        """
        Validate portfolio position data.

        Args:
            positions: Portfolio positions to validate
            market_value: Total portfolio market value

        Returns:
            True if portfolio data is valid

        Raises:
            ValidationError: If portfolio data is invalid
        """
        # Validate market value
        if market_value <= 0:
            raise ValidationError("Market value must be positive")

        # Validate positions
        for security_id, quantity in positions.items():
            # Validate security ID format
            if not self._is_valid_security_id(security_id):
                raise ValidationError(f"Invalid security ID format: {security_id}")

            # Validate quantity type
            if not isinstance(quantity, int):
                raise ValidationError(f"Quantity for {security_id} must be an integer")

            # Validate quantity value
            if quantity < 0:
                raise ValidationError(
                    f"Quantities must be non-negative, got {quantity} for {security_id}"
                )

        return True

    async def validate_optimization_result(
        self,
        result_positions: dict[str, int],
        model: InvestmentModel,
        prices: dict[str, Decimal],
        market_value: Decimal,
    ) -> bool:
        """
        Validate optimization result against constraints.

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
        # Basic validation of result positions
        await self.validate_portfolio_data(result_positions, market_value)

        # Validate that drift bounds are respected
        for position in model.positions:
            security_id = position.security_id
            result_quantity = result_positions.get(security_id, 0)

            if security_id in prices:
                result_value = Decimal(str(result_quantity)) * prices[security_id]

                # Check if within drift bounds
                is_within_bounds = position.drift_bounds.is_within_bounds(
                    current_value=result_value,
                    target_percentage=position.target.value,
                    market_value=market_value,
                )

                if not is_within_bounds:
                    raise ValidationError(
                        f"Optimization result for {security_id} violates drift bounds"
                    )

        return True

    async def validate_security_ids(self, security_ids: list[str]) -> bool:
        """
        Validate security ID format and uniqueness.

        Args:
            security_ids: List of security IDs to validate

        Returns:
            True if all security IDs are valid and unique

        Raises:
            ValidationError: If any security ID is invalid
        """
        if not security_ids:
            return True  # Empty list is valid

        # Check for duplicates
        if len(security_ids) != len(set(security_ids)):
            raise ValidationError("Duplicate security IDs found")

        # Validate each security ID
        for security_id in security_ids:
            if not self._is_valid_security_id(security_id):
                raise ValidationError(f"Invalid security ID format: {security_id}")

        return True

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
        # Check if percentage is a multiple of 0.005
        remainder = percentage % Decimal("0.005")
        if remainder != 0:
            raise ValidationError(f"Percentage {percentage} is not a multiple of 0.005")

        return True

    async def _validate_model_basic_fields(self, model: InvestmentModel) -> None:
        """Validate basic model fields."""
        # Validate name
        if not model.name or not model.name.strip():
            raise ValidationError("Model name cannot be empty")

        # Validate portfolios
        if not model.portfolios:
            raise ValidationError(
                "Model must be associated with at least one portfolio"
            )

        # Validate version
        if model.version < 1:
            raise ValidationError("Model version must be at least 1")

    async def _validate_target_sum_limit(self, model: InvestmentModel) -> None:
        """Validate that target sum does not exceed 95%."""
        total_target = sum(position.target.value for position in model.positions)

        if total_target > Decimal("0.95"):
            raise BusinessRuleViolationError(
                f"Target sum ({total_target:.1%}) exceeds maximum allowed (95%)"
            )

    async def _validate_position_count_limit(self, model: InvestmentModel) -> None:
        """Validate maximum 100 positions with non-zero targets."""
        non_zero_positions = sum(
            1 for position in model.positions if position.target.value > 0
        )

        if non_zero_positions > 100:
            raise BusinessRuleViolationError(
                f"Model has {non_zero_positions} non-zero positions, maximum allowed is 100"
            )

    async def _validate_target_precision(self, model: InvestmentModel) -> None:
        """Validate target percentage precision."""
        for position in model.positions:
            await self.validate_percentage_precision(position.target.value)

    async def _validate_security_uniqueness(self, model: InvestmentModel) -> None:
        """Validate security uniqueness within model."""
        security_ids = [position.security_id for position in model.positions]
        await self.validate_security_ids(security_ids)

    async def _validate_drift_bounds(self, model: InvestmentModel) -> None:
        """Validate drift bounds for all positions."""
        for position in model.positions:
            drift_bounds = position.drift_bounds

            # Basic validation (already done in DriftBounds __post_init__)
            if drift_bounds.low_drift > drift_bounds.high_drift:
                raise BusinessRuleViolationError(
                    f"Low drift ({drift_bounds.low_drift}) cannot exceed "
                    f"high drift ({drift_bounds.high_drift}) for {position.security_id}"
                )

    async def _validate_portfolio_associations(self, model: InvestmentModel) -> None:
        """Validate portfolio associations."""
        for portfolio_id in model.portfolios:
            if not isinstance(portfolio_id, str) or not portfolio_id.strip():
                raise ValidationError(f"Invalid portfolio ID: {portfolio_id}")

    def _is_valid_security_id(self, security_id: str) -> bool:
        """
        Validate security ID format.

        Args:
            security_id: Security ID to validate

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(security_id, str):
            return False

        if len(security_id) != 24:
            return False

        if not re.match(r'^[A-Za-z0-9]+$', security_id):
            return False

        return True
