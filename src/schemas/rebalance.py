"""
Pydantic schemas for portfolio rebalancing API contracts.

This module defines the data transfer objects (DTOs) for rebalancing operations:
- DriftDTO: Position drift analysis
- RebalanceDTO: Complete rebalancing results with transactions and drift analysis

All schemas include comprehensive validation for financial data and precise
handling of portfolio optimization results.
"""

import re
from decimal import Decimal
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.schemas.transactions import TransactionDTO


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


class RebalanceDTO(BaseModel):
    """
    Complete rebalancing results.

    Contains the full results of a portfolio rebalancing operation, including
    the list of transactions to execute and drift analysis for all positions.
    """

    model_config = ConfigDict(json_encoders={Decimal: str})

    portfolio_id: str = Field(
        ...,
        description="24-character alphanumeric portfolio identifier",
        min_length=24,
        max_length=24,
    )

    transactions: List[TransactionDTO] = Field(
        default_factory=list,
        description="List of transactions to execute for rebalancing",
    )

    drifts: List[DriftDTO] = Field(
        default_factory=list,
        description="Drift analysis for all positions in the portfolio",
    )

    @field_validator('portfolio_id')
    @classmethod
    def validate_portfolio_id(cls, v: str) -> str:
        """Validate portfolio ID format: exactly 24 alphanumeric characters."""
        if not re.match(r'^[A-Za-z0-9]{24}$', v):
            raise ValueError("Portfolio ID must be exactly 24 alphanumeric characters")
        return v
