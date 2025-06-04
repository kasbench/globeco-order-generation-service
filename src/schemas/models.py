"""
Pydantic schemas for investment model API contracts.

This module defines the data transfer objects (DTOs) for investment model operations:
- ModelPositionDTO: Position within an investment model
- ModelDTO: Complete investment model representation
- ModelPostDTO: Schema for model creation requests
- ModelPutDTO: Schema for model update requests
- ModelPortfolioDTO: Schema for portfolio association operations

All schemas include comprehensive validation, custom validators for financial data,
and bidirectional conversion methods to/from domain entities.
"""

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.entities.model import InvestmentModel, Position
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


class ModelPositionDTO(BaseModel):
    """
    Position within an investment model.

    Represents a security position with target allocation and drift tolerances.
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

    @field_validator('security_id')
    @classmethod
    def validate_security_id(cls, v: str) -> str:
        """Validate security ID format: exactly 24 alphanumeric characters."""
        if not re.match(r'^[A-Za-z0-9]{24}$', v):
            raise ValueError("Security ID must be exactly 24 alphanumeric characters")
        return v

    @field_validator('target')
    @classmethod
    def validate_target_precision(cls, v: Decimal) -> Decimal:
        """Validate target is zero or a multiple of 0.005."""
        if v == Decimal("0"):
            return v

        # Check if it's a multiple of 0.005
        remainder = v % Decimal("0.005")
        if remainder != Decimal("0"):
            raise ValueError("Target must be 0 or a multiple of 0.005")

        return v

    @model_validator(mode='after')
    def validate_drift_bounds(self):
        """Validate that low drift does not exceed high drift."""
        if self.low_drift > self.high_drift:
            raise ValueError("Low drift cannot exceed high drift")
        return self

    def to_domain(self) -> Position:
        """Convert DTO to domain Position entity."""
        return Position(
            security_id=self.security_id,
            target=TargetPercentage(self.target),
            drift_bounds=DriftBounds(
                low_drift=self.low_drift, high_drift=self.high_drift
            ),
        )

    @classmethod
    def from_domain(cls, position: Position) -> 'ModelPositionDTO':
        """Create DTO from domain Position entity."""
        return cls(
            security_id=position.security_id,
            target=position.target.value,
            high_drift=position.drift_bounds.high_drift,
            low_drift=position.drift_bounds.low_drift,
        )


class ModelDTO(BaseModel):
    """
    Complete investment model representation.

    Used for GET responses and complete model data transfer.
    """

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            datetime: lambda dt: dt.isoformat() if dt else None,
        }
    )

    model_id: str = Field(
        ..., description="Unique model identifier (24-character hex string)"
    )

    name: str = Field(..., description="Model name", min_length=1, max_length=255)

    positions: List[ModelPositionDTO] = Field(
        default_factory=list,
        description="Security positions in the model",
        max_length=100,
    )

    portfolios: List[str] = Field(
        ..., description="Associated portfolio IDs", min_length=1
    )

    last_rebalance_date: Optional[datetime] = Field(
        None, description="Last rebalancing timestamp (UTC)"
    )

    version: int = Field(..., description="Optimistic locking version", gt=0)

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Validate model name is not empty or whitespace only."""
        if not v.strip():
            raise ValueError("Model name cannot be empty or whitespace only")
        return v.strip()

    @field_validator('positions')
    @classmethod
    def validate_position_count(
        cls, v: List[ModelPositionDTO]
    ) -> List[ModelPositionDTO]:
        """Validate maximum number of positions."""
        if len(v) > 100:
            raise ValueError("Model cannot have more than 100 positions")
        return v

    @field_validator('portfolios')
    @classmethod
    def validate_portfolios_not_empty_and_unique(cls, v: List[str]) -> List[str]:
        """Validate portfolios list is not empty and contains no duplicates."""
        if len(v) == 0:
            raise ValueError("Model must be associated with at least one portfolio")

        if len(v) != len(set(v)):
            raise ValueError("Portfolio list cannot contain duplicate portfolio IDs")

        return v

    @model_validator(mode='after')
    def validate_target_sum(self):
        """Validate that sum of position targets does not exceed 0.95."""
        total_target = sum(position.target for position in self.positions)
        if total_target > Decimal("0.95"):
            raise ValueError("Sum of position targets cannot exceed 0.95 (95%)")
        return self

    def to_domain(self) -> InvestmentModel:
        """Convert DTO to domain InvestmentModel entity."""
        return InvestmentModel(
            model_id=self.model_id,
            name=self.name,
            positions=[position.to_domain() for position in self.positions],
            portfolios=self.portfolios,
            last_rebalance_date=self.last_rebalance_date,
            version=self.version,
        )

    @classmethod
    def from_domain(cls, model: InvestmentModel) -> 'ModelDTO':
        """Create DTO from domain InvestmentModel entity."""
        return cls(
            model_id=str(model.model_id),
            name=model.name,
            positions=[ModelPositionDTO.from_domain(pos) for pos in model.positions],
            portfolios=model.portfolios,
            last_rebalance_date=model.last_rebalance_date,
            version=model.version,
        )


class ModelPostDTO(BaseModel):
    """
    Schema for investment model creation requests.

    Used for POST /models endpoint.
    """

    model_config = ConfigDict(json_encoders={Decimal: str})

    name: str = Field(..., description="Model name", min_length=1, max_length=255)

    positions: List[ModelPositionDTO] = Field(
        default_factory=list, description="Initial security positions", max_length=100
    )

    portfolios: List[str] = Field(
        ..., description="Portfolio IDs to associate with model", min_length=1
    )

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Validate model name is not empty or whitespace only."""
        if not v.strip():
            raise ValueError("Model name cannot be empty or whitespace only")
        return v.strip()

    @field_validator('portfolios')
    @classmethod
    def validate_portfolios_unique(cls, v: List[str]) -> List[str]:
        """Validate portfolios list contains no duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Portfolio list cannot contain duplicate portfolio IDs")
        return v

    @model_validator(mode='after')
    def validate_target_sum(self):
        """Validate that sum of position targets does not exceed 0.95."""
        total_target = sum(position.target for position in self.positions)
        if total_target > Decimal("0.95"):
            raise ValueError("Sum of position targets cannot exceed 0.95 (95%)")
        return self


class ModelPutDTO(BaseModel):
    """
    Schema for investment model update requests.

    Used for PUT /model/{model_id} endpoint.
    """

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            datetime: lambda dt: dt.isoformat() if dt else None,
        }
    )

    name: str = Field(..., description="Model name", min_length=1, max_length=255)

    positions: List[ModelPositionDTO] = Field(
        default_factory=list, description="Updated security positions", max_length=100
    )

    portfolios: List[str] = Field(
        ..., description="Updated portfolio associations", min_length=1
    )

    last_rebalance_date: Optional[datetime] = Field(
        None, description="Last rebalancing timestamp (UTC)"
    )

    version: int = Field(
        ..., description="Current version for optimistic locking", gt=0
    )

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Validate model name is not empty or whitespace only."""
        if not v.strip():
            raise ValueError("Model name cannot be empty or whitespace only")
        return v.strip()

    @field_validator('portfolios')
    @classmethod
    def validate_portfolios_unique(cls, v: List[str]) -> List[str]:
        """Validate portfolios list contains no duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Portfolio list cannot contain duplicate portfolio IDs")
        return v

    @model_validator(mode='after')
    def validate_target_sum(self):
        """Validate that sum of position targets does not exceed 0.95."""
        total_target = sum(position.target for position in self.positions)
        if total_target > Decimal("0.95"):
            raise ValueError("Sum of position targets cannot exceed 0.95 (95%)")
        return self

    def to_domain(self, model_id: str) -> InvestmentModel:
        """Convert DTO to domain InvestmentModel entity for update."""
        return InvestmentModel(
            model_id=model_id,
            name=self.name,
            positions=[position.to_domain() for position in self.positions],
            portfolios=self.portfolios,
            last_rebalance_date=self.last_rebalance_date,
            version=self.version,
        )


class ModelPortfolioDTO(BaseModel):
    """
    Schema for portfolio association operations.

    Used for POST/DELETE /model/{model_id}/portfolio endpoints.
    """

    portfolios: List[str] = Field(
        ..., description="Portfolio IDs to add/remove", min_length=1
    )

    @field_validator('portfolios')
    @classmethod
    def validate_portfolios_unique(cls, v: List[str]) -> List[str]:
        """Validate portfolios list contains no duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Portfolio list cannot contain duplicate portfolio IDs")
        return v
