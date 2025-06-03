"""
Custom assertions for testing financial and mathematical operations.

This module provides specialized assertion functions for validating
portfolio optimization results, financial calculations, and mathematical
constraints.
"""

from decimal import Decimal
from typing import Any

import numpy as np


def assert_decimal_equal(actual: Decimal, expected: Decimal, places: int = 4) -> None:
    """
    Assert that two decimal values are equal within specified precision.

    Args:
        actual: The actual decimal value
        expected: The expected decimal value
        places: Number of decimal places to check (default: 4)

    Raises:
        AssertionError: If values are not equal within precision
    """
    tolerance = Decimal(f"1e-{places}")
    difference = abs(actual - expected)
    assert difference < tolerance, (
        f"Decimal values not equal within {places} places: "
        f"expected {expected}, got {actual}, difference {difference}"
    )


def assert_optimization_valid(
    quantities: list[int],
    prices: list[Decimal],
    target_percentages: list[Decimal],
    market_value: Decimal,
    low_drifts: list[Decimal],
    high_drifts: list[Decimal],
    tolerance: Decimal = Decimal("0.0001"),
) -> None:
    """
    Assert that an optimization result satisfies all portfolio constraints.

    Args:
        quantities: List of security quantities
        prices: List of security prices
        target_percentages: List of target allocation percentages
        market_value: Total portfolio market value
        low_drifts: List of lower drift tolerances
        high_drifts: List of upper drift tolerances
        tolerance: Numerical tolerance for constraint violations

    Raises:
        AssertionError: If any constraint is violated
    """
    assert (
        len(quantities)
        == len(prices)
        == len(target_percentages)
        == len(low_drifts)
        == len(high_drifts)
    ), "All input lists must have the same length"

    # Check that all quantities are non-negative integers
    for i, qty in enumerate(quantities):
        assert isinstance(qty, int) and qty >= 0, (
            f"Quantity {i} must be non-negative integer: {qty}"
        )

    # Check drift constraints for each position
    total_position_value = Decimal("0")
    for i, (qty, price, target, low_drift, high_drift) in enumerate(
        zip(
            quantities,
            prices,
            target_percentages,
            low_drifts,
            high_drifts,
            strict=False,
        )
    ):
        position_value = Decimal(qty) * price
        total_position_value += position_value

        target_value = market_value * target
        lower_bound = market_value * (target - low_drift)
        upper_bound = market_value * (target + high_drift)

        # Allow for small numerical tolerance
        assert (
            (lower_bound - tolerance) <= position_value <= (upper_bound + tolerance)
        ), (
            f"Position {i} drift constraint violated: "
            f"value={position_value}, target={target_value}, "
            f"bounds=[{lower_bound}, {upper_bound}], "
            f"security={i}, quantity={qty}, price={price}"
        )

    # Check market value conservation (allowing for cash remainder)
    cash_value = market_value - total_position_value
    assert cash_value >= -tolerance, (
        f"Negative cash position not allowed: {cash_value}, "
        f"total_position_value={total_position_value}, market_value={market_value}"
    )


def assert_portfolio_weights_valid(
    positions: dict[str, Any],
    total_market_value: Decimal,
    tolerance: Decimal = Decimal("0.01"),
) -> None:
    """
    Assert that portfolio position weights are valid.

    Args:
        positions: Dictionary of position data with market values
        total_market_value: Total portfolio market value
        tolerance: Tolerance for weight validation

    Raises:
        AssertionError: If weights are invalid
    """
    total_weight = Decimal("0")

    for security_id, position in positions.items():
        if "marketValue" in position:
            weight = position["marketValue"] / total_market_value
            assert Decimal("0") <= weight <= Decimal("1") + tolerance, (
                f"Invalid weight for {security_id}: {weight}"
            )
            total_weight += weight

    # Total weights should not exceed 100% (plus tolerance)
    assert total_weight <= Decimal("1") + tolerance, (
        f"Total portfolio weights exceed 100%: {total_weight}"
    )


def assert_transactions_valid(transactions: list[dict[str, Any]]) -> None:
    """
    Assert that transaction data is valid.

    Args:
        transactions: List of transaction dictionaries

    Raises:
        AssertionError: If any transaction is invalid
    """
    for i, transaction in enumerate(transactions):
        # Check required fields
        required_fields = ["transactionType", "securityId", "quantity", "tradeDate"]
        for field in required_fields:
            assert field in transaction, (
                f"Transaction {i} missing required field: {field}"
            )

        # Check transaction type
        assert transaction["transactionType"] in [
            "BUY",
            "SELL",
        ], f"Transaction {i} has invalid type: {transaction['transactionType']}"

        # Check quantity is positive integer
        quantity = transaction["quantity"]
        assert isinstance(quantity, int) and quantity > 0, (
            f"Transaction {i} has invalid quantity: {quantity}"
        )

        # Check security ID format (24 character hex string)
        security_id = transaction["securityId"]
        assert isinstance(security_id, str) and len(security_id) == 24, (
            f"Transaction {i} has invalid securityId: {security_id}"
        )


def assert_mathematical_precision(
    calculated_value: float, expected_value: float, relative_tolerance: float = 1e-10
) -> None:
    """
    Assert mathematical precision for numerical calculations.

    Args:
        calculated_value: Value calculated by the system
        expected_value: Expected mathematical value
        relative_tolerance: Relative tolerance for comparison

    Raises:
        AssertionError: If precision is not sufficient
    """
    if expected_value == 0:
        assert abs(calculated_value) < relative_tolerance, (
            f"Expected zero, got {calculated_value}"
        )
    else:
        relative_error = abs((calculated_value - expected_value) / expected_value)
        assert relative_error < relative_tolerance, (
            f"Mathematical precision error: expected {expected_value}, "
            f"got {calculated_value}, relative error {relative_error}"
        )


def assert_optimization_convergence(
    optimization_result: dict[str, Any], max_iterations: int = 1000
) -> None:
    """
    Assert that optimization algorithm converged successfully.

    Args:
        optimization_result: Result dictionary from optimization solver
        max_iterations: Maximum allowed iterations

    Raises:
        AssertionError: If optimization did not converge properly
    """
    assert "status" in optimization_result, "Optimization result missing status"

    status = optimization_result["status"]
    assert status in [
        "optimal",
        "optimal_inaccurate",
    ], f"Optimization did not converge: status={status}"

    if "num_iterations" in optimization_result:
        assert optimization_result["num_iterations"] <= max_iterations, (
            f"Optimization took too many iterations: {optimization_result['num_iterations']}"
        )

    if "objective_value" in optimization_result:
        objective_value = optimization_result["objective_value"]
        assert not np.isnan(objective_value) and not np.isinf(objective_value), (
            f"Invalid objective value: {objective_value}"
        )
