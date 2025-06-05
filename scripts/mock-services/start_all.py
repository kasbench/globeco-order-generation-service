#!/usr/bin/env python3
"""
Mock External Services for GlobeCo Order Generation Service Development

This module provides lightweight mock implementations of external services
for development and testing purposes.
"""

import asyncio
import json
import multiprocessing
import signal
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ============================================================================
# Mock Data Models
# ============================================================================


class PortfolioPosition(BaseModel):
    security_id: str = Field(..., description="24-character security identifier")
    quantity: int = Field(..., description="Number of shares")
    market_value: Decimal = Field(..., description="Current market value")


class Portfolio(BaseModel):
    portfolio_id: str = Field(..., description="Portfolio identifier")
    positions: List[PortfolioPosition] = Field(default_factory=list)
    total_value: Decimal = Field(..., description="Total portfolio value")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SecurityPrice(BaseModel):
    security_id: str = Field(..., description="24-character security identifier")
    price: Decimal = Field(..., description="Current market price per share")
    currency: str = Field(default="USD", description="Price currency")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Transaction(BaseModel):
    transaction_id: str = Field(..., description="Transaction identifier")
    portfolio_id: str = Field(..., description="Portfolio identifier")
    security_id: str = Field(..., description="Security identifier")
    transaction_type: str = Field(..., description="BUY or SELL")
    quantity: int = Field(..., description="Number of shares")
    price: Decimal = Field(..., description="Transaction price per share")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SecurityInfo(BaseModel):
    security_id: str = Field(..., description="24-character security identifier")
    symbol: str = Field(..., description="Trading symbol")
    name: str = Field(..., description="Security name")
    sector: str = Field(..., description="Business sector")
    market_cap: Decimal = Field(..., description="Market capitalization")


# ============================================================================
# Mock Service Applications
# ============================================================================


def create_portfolio_accounting_service() -> FastAPI:
    """Create Portfolio Accounting Service mock."""
    app = FastAPI(title="Mock Portfolio Accounting Service", version="1.0.0")

    # Mock portfolio data
    mock_portfolios = {
        "portfolio_123456789012345678901234": Portfolio(
            portfolio_id="portfolio_123456789012345678901234",
            positions=[
                PortfolioPosition(
                    security_id="AAPL000000000000000000001",
                    quantity=100,
                    market_value=Decimal("17500.00"),
                ),
                PortfolioPosition(
                    security_id="MSFT000000000000000000001",
                    quantity=50,
                    market_value=Decimal("21000.00"),
                ),
            ],
            total_value=Decimal("38500.00"),
        )
    }

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "portfolio_accounting"}

    @app.get("/portfolios/{portfolio_id}")
    async def get_portfolio(portfolio_id: str):
        if portfolio_id in mock_portfolios:
            return mock_portfolios[portfolio_id]
        raise HTTPException(status_code=404, detail="Portfolio not found")

    @app.post("/portfolios/{portfolio_id}/transactions")
    async def record_transaction(portfolio_id: str, transaction: Transaction):
        return {
            "transaction_id": f"txn_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "recorded",
            "portfolio_id": portfolio_id,
        }

    return app


def create_pricing_service() -> FastAPI:
    """Create Pricing Service mock."""
    app = FastAPI(title="Mock Pricing Service", version="1.0.0")

    # Mock pricing data
    mock_prices = {
        "AAPL000000000000000000001": SecurityPrice(
            security_id="AAPL000000000000000000001", price=Decimal("175.00")
        ),
        "MSFT000000000000000000001": SecurityPrice(
            security_id="MSFT000000000000000000001", price=Decimal("420.00")
        ),
        "GOOGL00000000000000000001": SecurityPrice(
            security_id="GOOGL00000000000000000001", price=Decimal("150.00")
        ),
    }

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "pricing"}

    @app.get("/prices/{security_id}")
    async def get_price(security_id: str):
        if security_id in mock_prices:
            return mock_prices[security_id]
        raise HTTPException(status_code=404, detail="Price not found")

    @app.post("/prices/bulk")
    async def get_bulk_prices(security_ids: List[str]):
        return [mock_prices[sid] for sid in security_ids if sid in mock_prices]

    return app


def create_portfolio_service() -> FastAPI:
    """Create Portfolio Service mock."""
    app = FastAPI(title="Mock Portfolio Service", version="1.0.0")

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "portfolio"}

    @app.get("/portfolios/{portfolio_id}/current-positions")
    async def get_current_positions(portfolio_id: str):
        return {
            "portfolio_id": portfolio_id,
            "positions": [
                {
                    "security_id": "AAPL000000000000000000001",
                    "quantity": 100,
                    "market_value": "17500.00",
                },
                {
                    "security_id": "MSFT000000000000000000001",
                    "quantity": 50,
                    "market_value": "21000.00",
                },
            ],
            "total_value": "38500.00",
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

    return app


def create_security_service() -> FastAPI:
    """Create Security Service mock."""
    app = FastAPI(title="Mock Security Service", version="1.0.0")

    # Mock security data
    mock_securities = {
        "AAPL000000000000000000001": SecurityInfo(
            security_id="AAPL000000000000000000001",
            symbol="AAPL",
            name="Apple Inc.",
            sector="Technology",
            market_cap=Decimal("2800000000000"),
        ),
        "MSFT000000000000000000001": SecurityInfo(
            security_id="MSFT000000000000000000001",
            symbol="MSFT",
            name="Microsoft Corporation",
            sector="Technology",
            market_cap=Decimal("3100000000000"),
        ),
    }

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "security"}

    @app.get("/securities/{security_id}")
    async def get_security(security_id: str):
        if security_id in mock_securities:
            return mock_securities[security_id]
        raise HTTPException(status_code=404, detail="Security not found")

    return app


# ============================================================================
# Service Runners
# ============================================================================


def run_service(service_name: str, port: int):
    """Run a mock service on the specified port."""
    if service_name == "portfolio_accounting":
        app = create_portfolio_accounting_service()
    elif service_name == "pricing":
        app = create_pricing_service()
    elif service_name == "portfolio":
        app = create_portfolio_service()
    elif service_name == "security":
        app = create_security_service()
    else:
        raise ValueError(f"Unknown service: {service_name}")

    print(f"Starting {service_name} service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}, shutting down mock services...")
    sys.exit(0)


def main():
    """Start all mock services."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    services = [
        ("portfolio_accounting", 8001),
        ("pricing", 8002),
        ("portfolio", 8003),
        ("security", 8004),
    ]

    print("Starting all mock services...")

    processes = []
    for service_name, port in services:
        process = multiprocessing.Process(target=run_service, args=(service_name, port))
        process.start()
        processes.append(process)

    try:
        # Wait for all processes
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        print("\nShutting down all mock services...")
        for process in processes:
            process.terminate()
            process.join()


if __name__ == "__main__":
    main()
