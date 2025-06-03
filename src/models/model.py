"""
Beanie ODM document models for MongoDB persistence.

This module defines the MongoDB document structure using Beanie ODM
for investment models and their associated positions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from beanie import Document
from bson import Decimal128, ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from pymongo import IndexModel

from src.domain.entities.model import InvestmentModel
from src.domain.entities.position import Position
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


class PositionEmbedded(BaseModel):
    """Embedded document for position data within investment models."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )

    security_id: str = Field(..., description="24-character security identifier")
    target: Decimal = Field(..., description="Target allocation percentage (0-0.95)")
    high_drift: Decimal = Field(..., description="Upper drift tolerance (0-1)")
    low_drift: Decimal = Field(..., description="Lower drift tolerance (0-1)")

    @field_validator('security_id')
    @classmethod
    def validate_security_id_format(cls, v):
        """Validate security ID format (24 alphanumeric characters)."""
        if not isinstance(v, str) or len(v) != 24 or not v.isalnum():
            raise ValueError("Security ID must be exactly 24 alphanumeric characters")
        return v

    @field_validator('target', 'high_drift', 'low_drift', mode='before')
    @classmethod
    def validate_decimal_fields(cls, v):
        """Convert Decimal128 to Decimal and validate ranges."""
        # Convert Decimal128 to Decimal if needed
        if isinstance(v, Decimal128):
            v = v.to_decimal()
        elif isinstance(v, (int, float, str)):
            v = Decimal(str(v))
        return v

    @field_validator('target')
    @classmethod
    def validate_target_range(cls, v):
        """Validate target percentage is within acceptable range."""
        if not (Decimal('0') <= v <= Decimal('0.95')):
            raise ValueError("Target must be between 0 and 0.95 (95%)")
        return v

    @field_validator('high_drift', 'low_drift')
    @classmethod
    def validate_drift_range(cls, v):
        """Validate drift values are within acceptable range."""
        if not (Decimal('0') <= v <= Decimal('1')):
            raise ValueError("Drift values must be between 0 and 1")
        return v

    @field_validator('high_drift')
    @classmethod
    def validate_drift_relationship(cls, v, info):
        """Validate that high_drift >= low_drift."""
        if 'low_drift' in info.data and v < info.data['low_drift']:
            raise ValueError("High drift must be >= low drift")
        return v

    @field_serializer('target', 'high_drift', 'low_drift')
    def serialize_decimal_fields(self, value: Decimal) -> Decimal128:
        """Serialize Decimal fields to Decimal128 for MongoDB storage."""
        return Decimal128(str(value))

    def to_domain_position(self) -> Position:
        """Convert embedded document to domain Position entity."""
        return Position(
            security_id=self.security_id,
            target=TargetPercentage(self.target),
            drift_bounds=DriftBounds(
                low_drift=self.low_drift, high_drift=self.high_drift
            ),
        )

    @classmethod
    def from_domain_position(cls, position: Position) -> 'PositionEmbedded':
        """Create embedded document from domain Position entity."""
        return cls(
            security_id=position.security_id,
            target=position.target.value,
            high_drift=position.drift_bounds.high_drift,
            low_drift=position.drift_bounds.low_drift,
        )


class ModelDocument(Document):
    """MongoDB document model for investment models using Beanie ODM."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )

    # Use ObjectId for _id field
    id: Optional[ObjectId] = Field(default_factory=ObjectId, alias="_id")

    name: str = Field(..., description="Unique model name")
    positions: List[PositionEmbedded] = Field(
        default_factory=list, description="List of security positions"
    )
    portfolios: List[str] = Field(
        default_factory=list, description="Associated portfolio identifiers"
    )
    last_rebalance_date: Optional[datetime] = Field(
        None, description="Last rebalancing timestamp"
    )
    version: int = Field(default=1, description="Version for optimistic locking")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v):
        """Validate model name is not empty."""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        return v.strip()

    @field_validator('positions')
    @classmethod
    def validate_position_targets_sum(cls, v):
        """Validate position targets sum to <= 0.95."""
        if not v:
            return v

        total_target = sum(pos.target for pos in v)
        if total_target > Decimal('0.95'):
            raise ValueError(
                f"Position targets sum {total_target} exceeds maximum 0.95"
            )
        return v

    @field_validator('positions')
    @classmethod
    def validate_position_count(cls, v):
        """Validate maximum 100 positions with non-zero targets."""
        if not v:
            return v

        non_zero_positions = [pos for pos in v if pos.target > 0]
        if len(non_zero_positions) > 100:
            raise ValueError(
                f"Maximum 100 non-zero positions allowed, got {len(non_zero_positions)}"
            )
        return v

    @field_validator('positions')
    @classmethod
    def validate_unique_securities(cls, v):
        """Validate no duplicate securities in positions."""
        if not v:
            return v

        security_ids = [pos.security_id for pos in v]
        if len(security_ids) != len(set(security_ids)):
            raise ValueError("Duplicate securities not allowed in model")
        return v

    @field_validator('portfolios')
    @classmethod
    def validate_unique_portfolios(cls, v):
        """Validate no duplicate portfolios."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate portfolios not allowed")
        return v

    @field_validator('version')
    @classmethod
    def validate_version_positive(cls, v):
        """Validate version is positive."""
        if v < 1:
            raise ValueError("Version must be positive")
        return v

    def to_domain_model(self) -> InvestmentModel:
        """Convert document to domain InvestmentModel entity."""
        return InvestmentModel(
            model_id=self.id,
            name=self.name,
            positions=[pos.to_domain_position() for pos in self.positions],
            portfolios=self.portfolios.copy(),
            last_rebalance_date=self.last_rebalance_date,
            version=self.version,
        )

    @classmethod
    def from_domain_model(cls, model: InvestmentModel) -> 'ModelDocument':
        """Create document from domain InvestmentModel entity."""
        return cls(
            id=model.model_id,
            name=model.name,
            positions=[
                PositionEmbedded.from_domain_position(pos) for pos in model.positions
            ],
            portfolios=model.portfolios.copy(),
            last_rebalance_date=model.last_rebalance_date,
            version=model.version,
            updated_at=datetime.utcnow(),
        )

    def update_from_domain_model(self, model: InvestmentModel) -> None:
        """Update document fields from domain model."""
        self.name = model.name
        self.positions = [
            PositionEmbedded.from_domain_position(pos) for pos in model.positions
        ]
        self.portfolios = model.portfolios.copy()
        self.last_rebalance_date = model.last_rebalance_date
        self.version = model.version
        self.updated_at = datetime.utcnow()

    class Settings:
        """Beanie document settings."""

        name = "models"  # Collection name

        # Define indexes for optimal query performance
        indexes = [
            # Unique index on name
            IndexModel([("name", 1)], unique=True),
            # Index on portfolios for filtering (multikey index)
            IndexModel([("portfolios", 1)]),
            # Index on last_rebalance_date for time-based queries
            IndexModel([("last_rebalance_date", 1)]),
            # Compound index on positions.security_id for security-based queries
            IndexModel([("positions.security_id", 1)]),
            # Index on version for optimistic locking
            IndexModel([("version", 1)]),
            # Index on created_at for chronological sorting
            IndexModel([("created_at", -1)]),
        ]
