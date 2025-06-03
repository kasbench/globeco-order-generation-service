"""
Helper utilities for test setup and cleanup operations.

This module provides utility functions for creating test models,
cleaning up test data, and other common test operations.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any


def create_test_model(
    name: str = "Test Model",
    positions: list[dict[str, Any]] | None = None,
    portfolios: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create a test investment model with default values.

    Args:
        name: Model name
        positions: List of position dictionaries
        portfolios: List of portfolio IDs

    Returns:
        Dictionary containing model data
    """
    if positions is None:
        positions = [
            {
                "securityId": "683b6b9620f302c879a5fef4",
                "target": Decimal("0.60"),
                "highDrift": Decimal("0.05"),
                "lowDrift": Decimal("0.05"),
            },
            {
                "securityId": "683b6b9620f302c879a5fef5",
                "target": Decimal("0.35"),
                "highDrift": Decimal("0.03"),
                "lowDrift": Decimal("0.03"),
            },
        ]

    if portfolios is None:
        portfolios = ["683b6d88a29ee10e8b499643"]

    return {
        "name": name,
        "positions": positions,
        "portfolios": portfolios,
        "lastRebalanceDate": None,
        "version": 1,
    }


async def cleanup_test_data(database) -> None:
    """
    Clean up test data from the database.

    Args:
        database: MongoDB database instance
    """
    # Drop all collections
    collection_names = await database.list_collection_names()
    for collection_name in collection_names:
        await database[collection_name].drop()


def validate_model_data(model_data: dict[str, Any]) -> bool:
    """
    Validate that model data conforms to expected structure.

    Args:
        model_data: Model data dictionary

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["name", "positions", "portfolios"]

    # Check required fields
    for field in required_fields:
        if field not in model_data:
            return False

    # Validate positions
    if not isinstance(model_data["positions"], list):
        return False

    for position in model_data["positions"]:
        position_fields = ["securityId", "target", "highDrift", "lowDrift"]
        for field in position_fields:
            if field not in position:
                return False

        # Validate constraints
        target = position["target"]
        high_drift = position["highDrift"]
        low_drift = position["lowDrift"]

        if not (0 <= target <= 1):
            return False
        if not (0 <= low_drift <= high_drift <= 1):
            return False

    # Validate target sum
    target_sum = sum(pos["target"] for pos in model_data["positions"])
    if target_sum > Decimal("0.95"):
        return False

    return True


def create_test_portfolio_balance(
    security_id: str, quantity: int, price: Decimal, is_cash: bool = False
) -> dict[str, Any]:
    """
    Create a test portfolio balance entry.

    Args:
        security_id: Security identifier
        quantity: Number of shares/units
        price: Price per share/unit
        is_cash: Whether this is a cash position

    Returns:
        Dictionary containing balance data
    """
    balance = {
        "securityId": security_id,
        "quantity": quantity,
        "marketValue": Decimal(quantity) * price,
    }

    if is_cash:
        balance["cash"] = True

    return balance


def create_test_transaction(
    transaction_type: str,
    security_id: str,
    quantity: int,
    trade_date: datetime | None = None,
) -> dict[str, Any]:
    """
    Create a test transaction.

    Args:
        transaction_type: "BUY" or "SELL"
        security_id: Security identifier
        quantity: Transaction quantity
        trade_date: Trade date (defaults to now)

    Returns:
        Dictionary containing transaction data
    """
    if trade_date is None:
        trade_date = datetime.now()

    return {
        "transactionType": transaction_type,
        "securityId": security_id,
        "quantity": quantity,
        "tradeDate": trade_date.date().isoformat(),
    }


def calculate_portfolio_total_value(positions: list[dict[str, Any]]) -> Decimal:
    """
    Calculate total portfolio value from positions.

    Args:
        positions: List of position dictionaries

    Returns:
        Total portfolio market value
    """
    return sum(pos.get("marketValue", Decimal("0")) for pos in positions)


def normalize_decimal_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize decimal values in a dictionary for comparison.

    Args:
        data: Dictionary that may contain Decimal values

    Returns:
        Dictionary with normalized Decimal values
    """
    normalized = {}

    for key, value in data.items():
        if isinstance(value, Decimal):
            normalized[key] = value.quantize(Decimal("0.0001"))
        elif isinstance(value, dict):
            normalized[key] = normalize_decimal_dict(value)
        elif isinstance(value, list):
            normalized[key] = [
                normalize_decimal_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            normalized[key] = value

    return normalized


def mock_external_service_response(
    service_name: str,
    success: bool = True,
    data: Any = None,
    error_message: str = "Service error",
) -> dict[str, Any]:
    """
    Create a mock response for external service calls.

    Args:
        service_name: Name of the service
        success: Whether the response indicates success
        data: Response data
        error_message: Error message for failed responses

    Returns:
        Mock response dictionary
    """
    if success:
        return {
            "status": "success",
            "data": data or {},
            "service": service_name,
            "timestamp": datetime.now().isoformat(),
        }
    else:
        return {
            "status": "error",
            "error": error_message,
            "service": service_name,
            "timestamp": datetime.now().isoformat(),
        }


def setup_test_logging(level: str = "DEBUG") -> None:
    """
    Set up logging for tests.

    Args:
        level: Log level to use for tests
    """
    import logging

    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,  # Override existing configuration
    )

    # Reduce noise from third-party libraries
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("cvxpy").setLevel(logging.WARNING)
