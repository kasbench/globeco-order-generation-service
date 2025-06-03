"""
Portfolio Drift Calculator implementation.

This module contains the concrete implementation of the DriftCalculator interface,
providing mathematical calculations for portfolio drift analysis with financial precision.
"""

import re
from decimal import Decimal

from src.core.exceptions import ValidationError
from src.domain.entities.model import InvestmentModel
from src.domain.services.drift_calculator import DriftCalculator, DriftInfo


class PortfolioDriftCalculator(DriftCalculator):
    """Concrete implementation of portfolio drift calculator."""

    async def calculate_portfolio_drift(
        self,
        positions: dict[str, int],
        prices: dict[str, Decimal],
        market_value: Decimal,
        model: InvestmentModel,
    ) -> list[DriftInfo]:
        """
        Calculate drift information for all positions in a portfolio.

        Args:
            positions: Current security quantities {security_id: quantity}
            prices: Current market prices {security_id: price}
            market_value: Total portfolio market value including cash
            model: Investment model with target allocations

        Returns:
            List of DriftInfo objects for each position in the model
        """
        # Validate inputs
        await self._validate_drift_inputs(positions, prices, market_value)

        drift_infos = []

        # Process each position in the model
        for position in model.positions:
            security_id = position.security_id

            # Get current quantity (0 if not held)
            current_quantity = positions.get(security_id, 0)

            # Get price for this security
            if security_id not in prices:
                raise ValidationError(f"Missing price for security {security_id}")

            price = prices[security_id]
            current_value = Decimal(str(current_quantity)) * price
            target_percentage = position.target.value
            target_value = market_value * target_percentage

            # Calculate drift
            drift_amount = await self.calculate_position_drift(
                current_value=current_value,
                target_percentage=target_percentage,
                market_value=market_value,
            )

            # Check if within bounds
            is_within_bounds = position.drift_bounds.is_within_bounds(
                current_value=current_value,
                target_percentage=target_percentage,
                market_value=market_value,
            )

            # Create drift info
            drift_info = DriftInfo(
                security_id=security_id,
                current_value=current_value,
                target_value=target_value,
                current_percentage=(
                    current_value / market_value if market_value > 0 else Decimal("0")
                ),
                target_percentage=target_percentage,
                drift_amount=drift_amount,
                is_within_bounds=is_within_bounds,
            )

            drift_infos.append(drift_info)

        return drift_infos

    async def calculate_position_drift(
        self, current_value: Decimal, target_percentage: Decimal, market_value: Decimal
    ) -> Decimal:
        """
        Calculate drift for a single position.

        Drift = (current_value / market_value) - target_percentage

        Args:
            current_value: Current market value of the position
            target_percentage: Target percentage allocation
            market_value: Total portfolio market value

        Returns:
            Drift amount (positive = above target, negative = below target)
        """
        if market_value == 0:
            raise ValidationError("Market value cannot be zero for drift calculation")

        current_percentage = current_value / market_value
        drift = current_percentage - target_percentage

        return drift

    async def calculate_total_drift(self, drift_infos: list[DriftInfo]) -> Decimal:
        """
        Calculate total portfolio drift as sum of absolute individual drifts.

        Total Drift = Σ|drift_amount_i|

        Args:
            drift_infos: List of individual position drift information

        Returns:
            Total absolute drift for the portfolio
        """
        total_drift = Decimal("0")

        for drift_info in drift_infos:
            total_drift += abs(drift_info.drift_amount)

        return total_drift

    async def get_positions_outside_bounds(
        self, drift_infos: list[DriftInfo]
    ) -> list[DriftInfo]:
        """
        Get positions that are outside their acceptable drift bounds.

        Args:
            drift_infos: List of position drift information

        Returns:
            List of DriftInfo for positions outside bounds
        """
        outside_bounds = []

        for drift_info in drift_infos:
            if not drift_info.is_within_bounds:
                outside_bounds.append(drift_info)

        return outside_bounds

    async def calculate_required_trades(
        self, current_positions: dict[str, int], target_positions: dict[str, int]
    ) -> dict[str, int]:
        """
        Calculate required trades to move from current to target positions.

        Args:
            current_positions: Current security quantities
            target_positions: Target security quantities

        Returns:
            Required trades {security_id: quantity_change}
            Positive = buy, negative = sell, zero = no change
        """
        trades = {}

        # Get all securities from both current and target positions
        all_securities = set(current_positions.keys()) | set(target_positions.keys())

        for security_id in all_securities:
            current_qty = current_positions.get(security_id, 0)
            target_qty = target_positions.get(security_id, 0)
            trade_qty = target_qty - current_qty

            # Only include non-zero trades
            if trade_qty != 0:
                trades[security_id] = trade_qty

        return trades

    async def estimate_trade_costs(
        self,
        trades: dict[str, int],
        prices: dict[str, Decimal],
        commission_rate: Decimal = Decimal("0.001"),  # 0.1% default
    ) -> Decimal:
        """
        Estimate total cost of executing trades.

        Args:
            trades: Required trades {security_id: quantity_change}
            prices: Current market prices
            commission_rate: Commission rate as decimal (e.g., 0.001 = 0.1%)

        Returns:
            Estimated total cost including commissions
        """
        total_cost = Decimal("0")

        for security_id, quantity_change in trades.items():
            if security_id not in prices:
                raise ValidationError(
                    f"Missing price for security {security_id} in trade cost calculation"
                )

            price = prices[security_id]
            trade_value = abs(quantity_change) * price
            commission = trade_value * commission_rate
            total_cost += commission

        return total_cost

    async def _validate_drift_inputs(
        self,
        positions: dict[str, int],
        prices: dict[str, Decimal],
        market_value: Decimal,
    ) -> None:
        """
        Validate inputs for drift calculations.

        Args:
            positions: Current security quantities
            prices: Current market prices
            market_value: Total portfolio market value

        Raises:
            ValidationError: If any input is invalid
        """
        # Validate market value
        if market_value <= 0:
            raise ValidationError("Market value must be positive")

        # Validate positions
        for security_id, quantity in positions.items():
            if not isinstance(quantity, int):
                raise ValidationError(f"Quantity for {security_id} must be an integer")

            if quantity < 0:
                raise ValidationError(f"Quantity for {security_id} cannot be negative")

            # Validate security ID format
            if not self._is_valid_security_id(security_id):
                raise ValidationError(f"Invalid security ID format: {security_id}")

        # Validate prices
        for security_id, price in prices.items():
            if not isinstance(price, Decimal):
                raise ValidationError(f"Price for {security_id} must be a Decimal")

            if price <= 0:
                raise ValidationError(f"Price for {security_id} must be positive")

            # Validate security ID format
            if not self._is_valid_security_id(security_id):
                raise ValidationError(f"Invalid security ID format: {security_id}")

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
