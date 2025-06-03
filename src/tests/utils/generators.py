"""
Test data generators for creating random test data.

This module provides functions to generate realistic test data for
portfolios, securities, prices, and investment models.
"""

import random
from decimal import Decimal
from typing import List, Dict, Any
from datetime import datetime, timedelta


def generate_test_securities(count: int = 10) -> List[Dict[str, Any]]:
    """
    Generate a list of test securities.

    Args:
        count: Number of securities to generate

    Returns:
        List of security dictionaries with IDs and metadata
    """
    securities = []

    # Sample security names and symbols
    companies = [
        ("Apple Inc", "AAPL"),
        ("Microsoft Corp", "MSFT"),
        ("Amazon.com Inc", "AMZN"),
        ("Alphabet Inc", "GOOGL"),
        ("Tesla Inc", "TSLA"),
        ("Meta Platforms", "META"),
        ("NVIDIA Corp", "NVDA"),
        ("Berkshire Hathaway", "BRK.B"),
        ("Johnson & Johnson", "JNJ"),
        ("JPMorgan Chase", "JPM"),
        ("Procter & Gamble", "PG"),
        ("Walmart Inc", "WMT"),
        ("Coca-Cola Co", "KO"),
        ("IBM Corp", "IBM"),
        ("Intel Corp", "INTC"),
    ]

    for i in range(count):
        company_name, symbol = companies[i % len(companies)]

        # Generate 24-character hex ID
        security_id = f"{i:024x}"  # Zero-padded hex ID

        securities.append(
            {
                "securityId": security_id,
                "symbol": f"{symbol}_{i}" if i >= len(companies) else symbol,
                "name": f"{company_name} {i}" if i >= len(companies) else company_name,
                "sector": random.choice(
                    ["Technology", "Healthcare", "Financial", "Consumer", "Industrial"]
                ),
                "marketCap": random.uniform(
                    1_000_000_000, 2_000_000_000_000
                ),  # $1B to $2T
                "currency": "USD",
            }
        )

    return securities


def generate_random_portfolio(
    securities: List[Dict[str, Any]],
    total_market_value: Decimal = Decimal("100000"),
    min_positions: int = 5,
    max_positions: int = 15,
    cash_percentage: Decimal = Decimal("0.05"),
) -> Dict[str, Any]:
    """
    Generate a random portfolio with realistic positions.

    Args:
        securities: List of available securities
        total_market_value: Total portfolio market value
        min_positions: Minimum number of positions
        max_positions: Maximum number of positions
        cash_percentage: Percentage to keep as cash

    Returns:
        Dictionary containing portfolio data with positions
    """
    num_positions = random.randint(min_positions, min(max_positions, len(securities)))
    selected_securities = random.sample(securities, num_positions)

    # Calculate available investment amount (excluding cash)
    investment_amount = total_market_value * (Decimal("1") - cash_percentage)

    # Generate random weights that sum to 1
    weights = [random.random() for _ in range(num_positions)]
    weight_sum = sum(weights)
    weights = [Decimal(str(w / weight_sum)) for w in weights]

    positions = []
    remaining_value = investment_amount

    for i, (security, weight) in enumerate(zip(selected_securities, weights)):
        if i == len(weights) - 1:
            # Last position gets remaining value to ensure exact total
            position_value = remaining_value
        else:
            position_value = investment_amount * weight
            remaining_value -= position_value

        # Generate random price between $10 and $500
        price = Decimal(str(random.uniform(10, 500))).quantize(Decimal("0.01"))

        # Calculate quantity (ensuring integer shares)
        quantity = int(position_value / price)
        actual_value = quantity * price

        positions.append(
            {
                "securityId": security["securityId"],
                "symbol": security["symbol"],
                "quantity": quantity,
                "price": price,
                "marketValue": actual_value,
            }
        )

    # Add cash position
    cash_value = total_market_value - sum(pos["marketValue"] for pos in positions)
    positions.append(
        {
            "securityId": "CASH",
            "symbol": "CASH",
            "quantity": 1,
            "price": cash_value,
            "marketValue": cash_value,
            "cash": True,
        }
    )

    portfolio_id = (
        f"{random.randint(1000000000000000000000000, 9999999999999999999999999):024x}"
    )

    return {
        "portfolioId": portfolio_id,
        "name": f"Test Portfolio {random.randint(1000, 9999)}",
        "totalMarketValue": total_market_value,
        "positions": positions,
        "lastUpdated": datetime.now().isoformat(),
    }


def generate_security_prices(
    security_ids: List[str],
    base_price_range: tuple = (10.0, 500.0),
    volatility: float = 0.1,
) -> Dict[str, Decimal]:
    """
    Generate realistic security prices.

    Args:
        security_ids: List of security IDs to generate prices for
        base_price_range: Tuple of (min_price, max_price) for base prices
        volatility: Price volatility factor (0.0 to 1.0)

    Returns:
        Dictionary mapping security IDs to prices
    """
    prices = {}

    for security_id in security_ids:
        if security_id == "CASH":
            prices[security_id] = Decimal("1.00")
            continue

        # Generate base price
        base_price = random.uniform(*base_price_range)

        # Add volatility
        volatility_factor = random.uniform(1 - volatility, 1 + volatility)
        final_price = base_price * volatility_factor

        # Round to 2 decimal places
        prices[security_id] = Decimal(str(final_price)).quantize(Decimal("0.01"))

    return prices


def generate_investment_model(
    securities: List[Dict[str, Any]],
    model_name: str = None,
    num_positions: int = None,
    target_sum_limit: Decimal = Decimal("0.95"),
) -> Dict[str, Any]:
    """
    Generate a realistic investment model.

    Args:
        securities: Available securities to choose from
        model_name: Name for the model (generated if None)
        num_positions: Number of positions (random if None)
        target_sum_limit: Maximum sum of target percentages

    Returns:
        Dictionary containing investment model data
    """
    if num_positions is None:
        num_positions = random.randint(3, min(10, len(securities)))

    if model_name is None:
        model_types = [
            "Conservative",
            "Moderate",
            "Aggressive",
            "Growth",
            "Value",
            "Balanced",
        ]
        model_name = f"{random.choice(model_types)} Model {random.randint(100, 999)}"

    selected_securities = random.sample(securities, num_positions)

    # Generate target percentages that sum to less than target_sum_limit
    targets = []
    remaining_target = target_sum_limit

    for i in range(num_positions):
        if i == num_positions - 1:
            # Last position gets remaining target (might be 0)
            target = min(remaining_target, Decimal("0.3"))  # Cap at 30%
        else:
            # Random target between 0.05 and 30% of remaining
            max_target = min(remaining_target * Decimal("0.6"), Decimal("0.3"))
            min_target = min(Decimal("0.005"), remaining_target)

            if max_target <= min_target:
                target = min_target
            else:
                target = Decimal(
                    str(random.uniform(float(min_target), float(max_target)))
                ).quantize(
                    Decimal("0.005")
                )  # Round to 0.5% increments

        targets.append(target)
        remaining_target -= target

        if remaining_target <= 0:
            break

    # Remove any zero targets and corresponding securities
    non_zero_targets = [
        (sec, tgt) for sec, tgt in zip(selected_securities, targets) if tgt > 0
    ]

    positions = []
    for security, target in non_zero_targets:
        # Generate drift tolerances
        high_drift = Decimal(str(random.uniform(0.01, 0.1))).quantize(Decimal("0.001"))
        low_drift = Decimal(str(random.uniform(0.01, float(high_drift)))).quantize(
            Decimal("0.001")
        )

        positions.append(
            {
                "securityId": security["securityId"],
                "target": target,
                "highDrift": high_drift,
                "lowDrift": low_drift,
            }
        )

    # Generate portfolio associations
    num_portfolios = random.randint(1, 3)
    portfolios = [
        f"{random.randint(1000000000000000000000000, 9999999999999999999999999):024x}"
        for _ in range(num_portfolios)
    ]

    return {
        "name": model_name,
        "positions": positions,
        "portfolios": portfolios,
        "lastRebalanceDate": None,
        "version": 1,
    }


def generate_optimization_problem(
    num_securities: int = 5,
    market_value: Decimal = Decimal("100000"),
    complexity: str = "simple",
) -> Dict[str, Any]:
    """
    Generate an optimization problem for testing.

    Args:
        num_securities: Number of securities in the problem
        market_value: Total portfolio market value
        complexity: Problem complexity ("simple", "medium", "complex")

    Returns:
        Dictionary containing optimization problem data
    """
    securities = generate_test_securities(num_securities)
    prices = generate_security_prices([s["securityId"] for s in securities])

    # Generate current quantities
    current_quantities = []
    for security in securities:
        price = prices[security["securityId"]]
        # Random quantity between 0 and max affordable
        max_qty = int(market_value / price * Decimal("0.2"))  # Max 20% in any position
        quantity = random.randint(0, max_qty)
        current_quantities.append(quantity)

    # Generate target model
    model = generate_investment_model(securities, num_positions=num_securities)

    # Extract optimization parameters
    target_percentages = [pos["target"] for pos in model["positions"]]
    low_drifts = [pos["lowDrift"] for pos in model["positions"]]
    high_drifts = [pos["highDrift"] for pos in model["positions"]]
    price_list = [prices[pos["securityId"]] for pos in model["positions"]]

    problem_data = {
        "securities": securities,
        "current_quantities": current_quantities,
        "target_percentages": target_percentages,
        "prices": price_list,
        "market_value": market_value,
        "low_drifts": low_drifts,
        "high_drifts": high_drifts,
        "model": model,
    }

    if complexity == "complex":
        # Add constraints to make problem more challenging
        problem_data["additional_constraints"] = {
            "max_position_size": Decimal("0.25"),  # No position > 25%
            "min_position_size": Decimal("0.01"),  # No position < 1%
            "sector_limits": {"Technology": Decimal("0.4")},  # Max 40% in tech
        }

    return problem_data
