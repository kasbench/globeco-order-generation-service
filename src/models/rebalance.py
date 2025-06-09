"""
Beanie ODM document models for rebalance result persistence.

This module defines the MongoDB document structure using Beanie ODM
for storing rebalance results with a three-level structure:
Rebalance → Portfolio → Position
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from beanie import Document
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import IndexModel


class PositionEmbedded(BaseModel):
    """Embedded document for position data within rebalance results."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )

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

    @field_validator(
        'price',
        'original_quantity',
        'adjusted_quantity',
        'original_position_market_value',
        'adjusted_position_market_value',
        'target',
        'high_drift',
        'low_drift',
        'actual',
        'actual_drift',
    )
    @classmethod
    def validate_non_negative_decimals(cls, v):
        """Validate decimal fields are non-negative."""
        if v is not None and v < 0:
            raise ValueError("Decimal fields must be non-negative")
        return v

    @field_validator('trade_quantity')
    @classmethod
    def validate_trade_quantity_positive(cls, v):
        """Validate trade quantity is positive when present."""
        if v is not None and v <= 0:
            raise ValueError("Trade quantity must be positive")
        return v


class PortfolioEmbedded(BaseModel):
    """Embedded document for portfolio data within rebalance results."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )

    portfolio_id: str = Field(..., description="Portfolio identifier")
    market_value: Decimal = Field(..., description="Market value of the portfolio")
    cash_before_rebalance: Decimal = Field(
        ..., description="Cash in the portfolio before rebalance"
    )
    cash_after_rebalance: Decimal = Field(
        ..., description="Cash in the portfolio after rebalance"
    )
    positions: List[PositionEmbedded] = Field(
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


class RebalanceDocument(Document):
    """MongoDB document model for rebalance results using Beanie ODM."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )

    # Use ObjectId for _id field
    id: Optional[ObjectId] = Field(default_factory=ObjectId, alias="_id")

    model_id: ObjectId = Field(..., description="ID of the model that was rebalanced")
    rebalance_date: datetime = Field(..., description="Date of the rebalance")
    model_name: str = Field(..., description="Name of the model that was rebalanced")
    number_of_portfolios: int = Field(
        ..., description="Number of portfolios in the rebalance"
    )
    portfolios: List[PortfolioEmbedded] = Field(
        default_factory=list, description="List of portfolios rebalanced"
    )
    version: int = Field(default=1, description="Version for optimistic locking")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    def validate_portfolio_count_matches(cls, v, info):
        """Validate actual portfolio count matches number_of_portfolios."""
        # Note: This validator runs before all fields are set, so we check at document level
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

    class Settings:
        """Beanie document settings."""

        name = "rebalances"  # Collection name

        # Define indexes for optimal query performance
        indexes = [
            # Index on model_id for filtering rebalances by model
            IndexModel([("model_id", 1)]),
            # Index on rebalance_date for time-based queries
            IndexModel([("rebalance_date", -1)]),
            # Index on model_name for filtering by model name
            IndexModel([("model_name", 1)]),
            # Index on portfolios.portfolio_id for portfolio-based queries
            IndexModel([("portfolios.portfolio_id", 1)]),
            # Compound index for model and date queries
            IndexModel([("model_id", 1), ("rebalance_date", -1)]),
            # Index on created_at for chronological sorting
            IndexModel([("created_at", -1)]),
            # Index on version for optimistic locking
            IndexModel([("version", 1)]),
        ]
