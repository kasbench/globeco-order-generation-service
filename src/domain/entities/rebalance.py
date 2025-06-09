"""
Domain entities for rebalance results.

This module defines the domain entities representing rebalance operations
with a three-level structure: Rebalance → Portfolio → Position
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RebalancePosition(BaseModel):
    """Domain entity representing a position within a rebalanced portfolio."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    security_id: str = Field(..., description="Security identifier")
    price: Decimal = Field(..., description="Price used for the rebalance")
    original_quantity: Decimal = Field(..., description="Original value of u")
    adjusted_quantity: Decimal = Field(..., description="New value of u'")
    original_position_market_value: Decimal = Field(
        ..., description="Original quantity times price"
    )
    adjusted_position_market_value: Decimal = Field(
        ..., description="Adjusted quantity times price"
    )
    target: Decimal = Field(..., description="Target from the model")
    high_drift: Decimal = Field(..., description="High drift from the model")
    low_drift: Decimal = Field(..., description="Low drift from the model")
    actual: Decimal = Field(..., description="(u' * p) / MV")
    actual_drift: Decimal = Field(..., description="1 - (actual/target)")
    transaction_type: Optional[str] = Field(
        None, description="'BUY' or 'SELL' or None if no transaction"
    )
    trade_quantity: Optional[int] = Field(
        None, description="Positive quantity to BUY or SELL"
    )
    trade_date: Optional[datetime] = Field(None, description="Current date (no time)")

    @field_validator('security_id')
    @classmethod
    def validate_security_id_format(cls, v):
        """Validate security ID format (24 alphanumeric characters)."""
        if not isinstance(v, str) or len(v) != 24 or not v.isalnum():
            raise ValueError("Security ID must be exactly 24 alphanumeric characters")
        return v

    @field_validator('transaction_type')
    @classmethod
    def validate_transaction_type(cls, v):
        """Validate transaction type is BUY or SELL."""
        if v is not None and v not in ('BUY', 'SELL'):
            raise ValueError("Transaction type must be 'BUY' or 'SELL'")
        return v

    @field_validator('trade_quantity')
    @classmethod
    def validate_trade_quantity_positive(cls, v):
        """Validate trade quantity is positive when present."""
        if v is not None and v <= 0:
            raise ValueError("Trade quantity must be positive")
        return v

    def calculate_transaction_delta(self) -> int:
        """Calculate the transaction delta (adjusted - original)."""
        return int(self.adjusted_quantity - self.original_quantity)

    def has_transaction(self) -> bool:
        """Check if this position has an associated transaction."""
        return self.transaction_type is not None and self.trade_quantity is not None


class RebalancePortfolio(BaseModel):
    """Domain entity representing a portfolio within a rebalance operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    portfolio_id: str = Field(..., description="Portfolio identifier")
    market_value: Decimal = Field(..., description="Market value of the portfolio")
    cash_before_rebalance: Decimal = Field(
        ..., description="Cash in the portfolio before rebalance"
    )
    cash_after_rebalance: Decimal = Field(
        ..., description="Cash in the portfolio after rebalance"
    )
    positions: List[RebalancePosition] = Field(
        default_factory=list, description="List of positions in the portfolio"
    )

    @field_validator('portfolio_id')
    @classmethod
    def validate_portfolio_id_format(cls, v):
        """Validate portfolio ID format (24-character string)."""
        if not isinstance(v, str) or len(v) != 24:
            raise ValueError("Portfolio ID must be exactly 24 characters")
        return v

    @field_validator('market_value', 'cash_before_rebalance', 'cash_after_rebalance')
    @classmethod
    def validate_non_negative_values(cls, v):
        """Validate monetary values are non-negative."""
        if v < 0:
            raise ValueError("Monetary values must be non-negative")
        return v

    @field_validator('positions')
    @classmethod
    def validate_unique_securities_in_positions(cls, v):
        """Validate no duplicate securities in positions."""
        if not v:
            return v

        security_ids = [pos.security_id for pos in v]
        if len(security_ids) != len(set(security_ids)):
            raise ValueError("Duplicate securities not allowed in portfolio positions")
        return v

    def get_position_by_security(self, security_id: str) -> Optional[RebalancePosition]:
        """Get a position by security ID."""
        for position in self.positions:
            if position.security_id == security_id:
                return position
        return None

    def get_transaction_count(self) -> int:
        """Get the total number of transactions in this portfolio."""
        return sum(1 for pos in self.positions if pos.has_transaction())

    def calculate_total_original_market_value(self) -> Decimal:
        """Calculate total original market value of all positions."""
        return sum(pos.original_position_market_value for pos in self.positions)

    def calculate_total_adjusted_market_value(self) -> Decimal:
        """Calculate total adjusted market value of all positions."""
        return sum(pos.adjusted_position_market_value for pos in self.positions)


class Rebalance(BaseModel):
    """Domain entity representing a complete rebalance operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    rebalance_id: Optional[ObjectId] = Field(
        None, description="Unique rebalance identifier"
    )
    model_id: ObjectId = Field(..., description="ID of the model that was rebalanced")
    rebalance_date: datetime = Field(..., description="Date of the rebalance")
    model_name: str = Field(..., description="Name of the model that was rebalanced")
    number_of_portfolios: int = Field(
        ..., description="Number of portfolios in the rebalance"
    )
    portfolios: List[RebalancePortfolio] = Field(
        default_factory=list, description="List of portfolios rebalanced"
    )
    version: int = Field(default=1, description="Version for optimistic locking")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")

    @field_validator('model_name')
    @classmethod
    def validate_model_name_not_empty(cls, v):
        """Validate model name is not empty."""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        return v.strip()

    @field_validator('number_of_portfolios')
    @classmethod
    def validate_number_of_portfolios_positive(cls, v):
        """Validate number of portfolios is positive."""
        if v <= 0:
            raise ValueError("Number of portfolios must be positive")
        return v

    @field_validator('portfolios')
    @classmethod
    def validate_unique_portfolios(cls, v):
        """Validate no duplicate portfolios."""
        if not v:
            return v

        portfolio_ids = [portfolio.portfolio_id for portfolio in v]
        if len(portfolio_ids) != len(set(portfolio_ids)):
            raise ValueError("Duplicate portfolios not allowed in rebalance")
        return v

    @field_validator('version')
    @classmethod
    def validate_version_positive(cls, v):
        """Validate version is positive."""
        if v < 1:
            raise ValueError("Version must be positive")
        return v

    def validate_portfolio_count_consistency(self) -> None:
        """Validate that the number of portfolios matches the actual count."""
        if len(self.portfolios) != self.number_of_portfolios:
            raise ValueError(
                f"Portfolio count mismatch: expected {self.number_of_portfolios}, "
                f"got {len(self.portfolios)}"
            )

    def get_portfolio_by_id(self, portfolio_id: str) -> Optional[RebalancePortfolio]:
        """Get a portfolio by its ID."""
        for portfolio in self.portfolios:
            if portfolio.portfolio_id == portfolio_id:
                return portfolio
        return None

    def get_total_transaction_count(self) -> int:
        """Get the total number of transactions across all portfolios."""
        return sum(portfolio.get_transaction_count() for portfolio in self.portfolios)

    def get_portfolio_ids(self) -> List[str]:
        """Get list of all portfolio IDs in this rebalance."""
        return [portfolio.portfolio_id for portfolio in self.portfolios]

    def calculate_total_market_value(self) -> Decimal:
        """Calculate total market value across all portfolios."""
        return sum(portfolio.market_value for portfolio in self.portfolios)
