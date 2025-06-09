"""
Pydantic schemas for rebalance data transfer objects.

This module defines the API contracts for rebalance-related operations,
including request and response DTOs.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.schemas.transactions import TransactionDTO


class RebalancePositionDTO(BaseModel):
    """DTO for a position within a rebalanced portfolio."""

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
    actual_drift: Decimal = Field(..., description="(actual/target) - 1")
    transaction_type: Optional[str] = Field(
        None, description="'BUY' or 'SELL' or None if no transaction"
    )
    trade_quantity: Optional[int] = Field(
        None, description="Positive quantity to BUY or SELL"
    )
    trade_date: Optional[datetime] = Field(None, description="Current date (no time)")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat() if v else None,
        }


class RebalancePortfolioDTO(BaseModel):
    """DTO for a portfolio within a rebalance operation."""

    portfolio_id: str = Field(..., description="Portfolio identifier")
    market_value: Decimal = Field(..., description="Market value of the portfolio")
    cash_before_rebalance: Decimal = Field(
        ..., description="Cash in the portfolio before rebalance"
    )
    cash_after_rebalance: Decimal = Field(
        ..., description="Cash in the portfolio after rebalance"
    )
    positions: List[RebalancePositionDTO] = Field(
        default_factory=list, description="List of positions in the portfolio"
    )

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }


class RebalanceResultDTO(BaseModel):
    """DTO for a complete rebalance operation (new API)."""

    rebalance_id: str = Field(..., description="Unique rebalance identifier")
    model_id: str = Field(..., description="ID of the model that was rebalanced")
    rebalance_date: datetime = Field(..., description="Date of the rebalance")
    model_name: str = Field(..., description="Name of the model that was rebalanced")
    number_of_portfolios: int = Field(
        ..., description="Number of portfolios in the rebalance"
    )
    portfolios: List[RebalancePortfolioDTO] = Field(
        default_factory=list, description="List of portfolios rebalanced"
    )
    version: int = Field(default=1, description="Version for optimistic locking")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_validator('rebalance_id', 'model_id')
    @classmethod
    def validate_object_id_format(cls, v):
        """Validate ObjectId string format."""
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId format")
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class RebalancesByPortfoliosRequestDTO(BaseModel):
    """Request DTO for retrieving rebalances by portfolios."""

    portfolios: List[str] = Field(..., description="List of portfolio IDs to filter by")

    @field_validator('portfolios')
    @classmethod
    def validate_portfolios_not_empty(cls, v):
        """Validate portfolios list is not empty."""
        if not v:
            raise ValueError("Portfolios list cannot be empty")
        return v

    @field_validator('portfolios')
    @classmethod
    def validate_portfolio_id_lengths(cls, v):
        """Validate portfolio ID format (24-character strings)."""
        for portfolio_id in v:
            if not isinstance(portfolio_id, str) or len(portfolio_id) != 24:
                raise ValueError("Portfolio IDs must be exactly 24 characters")
        return v


# The original RebalanceDTO (for backward compatibility)
class RebalanceDTO(BaseModel):
    """Original DTO for backward compatibility with existing rebalance API."""

    portfolio_id: str = Field(
        ..., description="Portfolio identifier", min_length=24, max_length=24
    )
    rebalance_id: str = Field(..., description="Rebalance record identifier")
    transactions: List["TransactionDTO"] = Field(
        default_factory=list, description="List of transactions"
    )
    drifts: List["DriftDTO"] = Field(
        default_factory=list, description="List of drift information"
    )

    @field_validator('rebalance_id')
    @classmethod
    def validate_rebalance_id_format(cls, v):
        """Validate ObjectId string format."""
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId format")
        return v


class DriftDTO(BaseModel):
    """
    Position drift analysis.

    Represents the analysis of a security position's drift from target allocation,
    including original and adjusted quantities, target percentages, and actual
    allocation after rebalancing.
    """

    model_config = ConfigDict(
        json_encoders={Decimal: str}  # Serialize Decimal as string for JSON
    )

    security_id: str = Field(
        ...,
        description="24-character alphanumeric security identifier",
        min_length=24,
        max_length=24,
    )

    original_quantity: Decimal = Field(
        ..., description="Original quantity before rebalancing", ge=Decimal("0")
    )

    adjusted_quantity: Decimal = Field(
        ..., description="Adjusted quantity after rebalancing", ge=Decimal("0")
    )

    target: Decimal = Field(
        ...,
        description="Target allocation percentage (0-0.95)",
        ge=Decimal("0"),
        le=Decimal("0.95"),
    )

    high_drift: Decimal = Field(
        ...,
        description="Maximum allowable drift above target (0-1)",
        ge=Decimal("0"),
        le=Decimal("1"),
    )

    low_drift: Decimal = Field(
        ...,
        description="Maximum allowable drift below target (0-1)",
        ge=Decimal("0"),
        le=Decimal("1"),
    )

    actual: Decimal = Field(
        ...,
        description="Actual allocation percentage after rebalancing (4 decimal places)",
    )

    @field_validator('security_id')
    @classmethod
    def validate_security_id(cls, v: str) -> str:
        """Validate security ID format: exactly 24 alphanumeric characters."""
        import re

        if not re.match(r'^[A-Za-z0-9]{24}$', v):
            raise ValueError("Security ID must be exactly 24 alphanumeric characters")
        return v

    @field_validator('target')
    @classmethod
    def validate_target_range(cls, v: Decimal) -> Decimal:
        """Validate target percentage is within allowed range."""
        if v < Decimal("0") or v > Decimal("0.95"):
            raise ValueError("Target must be between 0 and 0.95")
        return v

    @field_validator('original_quantity', 'adjusted_quantity')
    @classmethod
    def validate_quantities_non_negative(cls, v: Decimal) -> Decimal:
        """Validate quantities are non-negative."""
        if v < Decimal("0"):
            raise ValueError("Quantities must be non-negative")
        return v

    @model_validator(mode='after')
    def validate_drift_bounds(self):
        """Validate that low drift does not exceed high drift."""
        if self.low_drift > self.high_drift:
            raise ValueError("Low drift cannot exceed high drift")
        return self


# Forward reference resolution
RebalanceDTO.model_rebuild()
