"""
Tests for Pydantic model schemas and API contracts.

This module tests the data transfer objects (DTOs) used for API communication:
- ModelDTO validation and serialization
- ModelPostDTO and ModelPutDTO for CRUD operations
- ModelPositionDTO for position management
- ModelPortfolioDTO for portfolio associations
- Complex validation scenarios and edge cases
- Serialization/deserialization accuracy
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.core.exceptions import ValidationError as DomainValidationError
from src.domain.entities.model import InvestmentModel, Position
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


@pytest.mark.unit
class TestModelPositionDTO:
    """Test ModelPositionDTO validation and conversion."""

    def test_valid_position_dto_creation(self):
        """Test creation of valid position DTO."""
        from src.schemas.models import ModelPositionDTO

        position_data = {
            "security_id": "STOCK1234567890123456789",
            "target": Decimal("0.25"),  # Multiple of 0.005
            "high_drift": Decimal("0.05"),
            "low_drift": Decimal("0.03"),
        }

        position_dto = ModelPositionDTO(**position_data)

        assert position_dto.security_id == "STOCK1234567890123456789"
        assert position_dto.target == Decimal("0.25")
        assert position_dto.high_drift == Decimal("0.05")
        assert position_dto.low_drift == Decimal("0.03")

    def test_position_dto_security_id_validation(self):
        """Test security ID validation requirements."""
        from src.schemas.models import ModelPositionDTO

        # Test invalid length (23 characters)
        with pytest.raises(ValidationError, match="at least 24 characters"):
            ModelPositionDTO(
                security_id="STOCK123456789012345678",  # 23 chars
                target=Decimal("0.25"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            )

        # Test invalid length (25 characters)
        with pytest.raises(ValidationError, match="at most 24 characters"):
            ModelPositionDTO(
                security_id="STOCK12345678901234567890",  # 25 chars
                target=Decimal("0.25"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            )

        # Test invalid characters (underscore)
        with pytest.raises(ValidationError, match="exactly 24.*alphanumeric"):
            ModelPositionDTO(
                security_id="STOCK123456789012345_789",  # 24 chars with underscore
                target=Decimal("0.25"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            )

    def test_position_dto_target_validation(self):
        """Test target percentage validation."""
        from src.schemas.models import ModelPositionDTO

        # Test target too high (> 0.95)
        with pytest.raises(ValidationError, match="less than or equal to 0.95"):
            ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("0.96"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            )

        # Test negative target
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("-0.05"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            )

        # Test invalid precision (not multiple of 0.005)
        with pytest.raises(ValidationError, match="multiple of 0.005"):
            ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("0.123"),  # Not multiple of 0.005
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            )

    def test_position_dto_drift_validation(self):
        """Test drift bounds validation."""
        from src.schemas.models import ModelPositionDTO

        # Test drift out of range (> 1.0)
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("0.25"),
                high_drift=Decimal("1.5"),  # Too high
                low_drift=Decimal("0.03"),
            )

        # Test negative drift
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("0.25"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("-0.01"),  # Negative
            )

        # Test low drift > high drift
        with pytest.raises(
            ValidationError, match="Low drift.*cannot exceed.*high drift"
        ):
            ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("0.25"),
                high_drift=Decimal("0.03"),
                low_drift=Decimal("0.05"),  # Higher than high_drift
            )

    def test_position_dto_to_domain_conversion(self):
        """Test conversion from DTO to domain Position."""
        from src.schemas.models import ModelPositionDTO

        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.30"),
            high_drift=Decimal("0.06"),
            low_drift=Decimal("0.04"),
        )

        domain_position = position_dto.to_domain()

        assert isinstance(domain_position, Position)
        assert domain_position.security_id == "STOCK1234567890123456789"
        assert domain_position.target.value == Decimal("0.30")
        assert domain_position.drift_bounds.high_drift == Decimal("0.06")
        assert domain_position.drift_bounds.low_drift == Decimal("0.04")

    def test_position_dto_from_domain_conversion(self):
        """Test conversion from domain Position to DTO."""
        from src.schemas.models import ModelPositionDTO

        domain_position = Position(
            security_id="BOND1111111111111111111A",
            target=TargetPercentage(Decimal("0.40")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.08")
            ),
        )

        position_dto = ModelPositionDTO.from_domain(domain_position)

        assert position_dto.security_id == "BOND1111111111111111111A"
        assert position_dto.target == Decimal("0.40")
        assert position_dto.high_drift == Decimal("0.08")
        assert position_dto.low_drift == Decimal("0.02")


@pytest.mark.unit
class TestModelDTO:
    """Test ModelDTO validation and conversion."""

    def test_valid_model_dto_creation(self):
        """Test creation of valid model DTO."""
        from src.schemas.models import ModelDTO, ModelPositionDTO

        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.60"),
            high_drift=Decimal("0.05"),
            low_drift=Decimal("0.03"),
        )

        model_data = {
            "model_id": "507f1f77bcf86cd799439011",
            "name": "Test Investment Model",
            "positions": [position_dto],
            "portfolios": ["683b6d88a29ee10e8b499643"],
            "last_rebalance_date": datetime(
                2024, 12, 19, 10, 30, 0, tzinfo=timezone.utc
            ),
            "version": 1,
        }

        model_dto = ModelDTO(**model_data)

        assert model_dto.model_id == "507f1f77bcf86cd799439011"
        assert model_dto.name == "Test Investment Model"
        assert len(model_dto.positions) == 1
        assert len(model_dto.portfolios) == 1
        assert model_dto.version == 1

    def test_model_dto_name_validation(self):
        """Test model name validation."""
        from src.schemas.models import ModelDTO

        # Test empty name
        with pytest.raises(ValidationError, match="at least 1 character"):
            ModelDTO(
                model_id="507f1f77bcf86cd799439011",
                name="",  # Empty name
                positions=[],
                portfolios=["portfolio1"],
                version=1,
            )

        # Test whitespace-only name
        with pytest.raises(ValidationError, match="cannot be empty"):
            ModelDTO(
                model_id="507f1f77bcf86cd799439011",
                name="   ",  # Whitespace only
                positions=[],
                portfolios=["portfolio1"],
                version=1,
            )

    def test_model_dto_positions_validation(self):
        """Test positions list validation."""
        from src.schemas.models import ModelDTO, ModelPositionDTO

        # Test too many positions (> 100)
        many_positions = []
        for i in range(101):
            many_positions.append(
                ModelPositionDTO(
                    security_id=f"STOCK{i:019d}",
                    target=Decimal("0.005"),  # Small targets to stay under 95%
                    high_drift=Decimal("0.02"),
                    low_drift=Decimal("0.02"),
                )
            )

        with pytest.raises(ValidationError, match="at most 100 items"):
            ModelDTO(
                model_id="507f1f77bcf86cd799439011",
                name="Too Many Positions",
                positions=many_positions,
                portfolios=["portfolio1"],
                version=1,
            )

    def test_model_dto_target_sum_validation(self):
        """Test that position targets sum validation."""
        from src.schemas.models import ModelDTO, ModelPositionDTO

        # Test targets sum > 0.95
        positions = [
            ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("0.50"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            ),
            ModelPositionDTO(
                security_id="BOND1111111111111111111A",
                target=Decimal("0.50"),  # Total = 1.00 > 0.95
                high_drift=Decimal("0.02"),
                low_drift=Decimal("0.02"),
            ),
        ]

        with pytest.raises(
            ValidationError, match="Sum of position targets cannot exceed 0.95"
        ):
            ModelDTO(
                model_id="507f1f77bcf86cd799439011",
                name="Invalid Target Sum",
                positions=positions,
                portfolios=["portfolio1"],
                version=1,
            )

    def test_model_dto_portfolios_validation(self):
        """Test portfolios list validation."""
        from src.schemas.models import ModelDTO

        # Test empty portfolios list
        with pytest.raises(ValidationError, match="at least 1 item"):
            ModelDTO(
                model_id="507f1f77bcf86cd799439011",
                name="No Portfolios",
                positions=[],
                portfolios=[],  # Empty portfolios
                version=1,
            )

        # Test duplicate portfolios
        with pytest.raises(ValidationError, match="duplicate portfolio IDs"):
            ModelDTO(
                model_id="507f1f77bcf86cd799439011",
                name="Duplicate Portfolios",
                positions=[],
                portfolios=["portfolio1", "portfolio1"],  # Duplicates
                version=1,
            )

    def test_model_dto_version_validation(self):
        """Test version field validation."""
        from src.schemas.models import ModelDTO

        # Test negative version
        with pytest.raises(ValidationError, match="greater than 0"):
            ModelDTO(
                model_id="507f1f77bcf86cd799439011",
                name="Invalid Version",
                positions=[],
                portfolios=["portfolio1"],
                version=-1,  # Negative version
            )

        # Test zero version
        with pytest.raises(ValidationError, match="greater than 0"):
            ModelDTO(
                model_id="507f1f77bcf86cd799439011",
                name="Zero Version",
                positions=[],
                portfolios=["portfolio1"],
                version=0,  # Zero version
            )

    def test_model_dto_to_domain_conversion(self):
        """Test conversion from ModelDTO to domain."""
        from src.schemas.models import ModelDTO, ModelPositionDTO

        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.75"),
            high_drift=Decimal("0.06"),
            low_drift=Decimal("0.04"),
        )

        model_dto = ModelDTO(
            model_id="507f1f77bcf86cd799439011",
            name="Test Model",
            positions=[position_dto],
            portfolios=["683b6d88a29ee10e8b499643"],
            version=2,
        )

        domain_model = model_dto.to_domain()

        assert isinstance(domain_model, InvestmentModel)
        assert str(domain_model.model_id) == "507f1f77bcf86cd799439011"
        assert domain_model.name == "Test Model"
        assert len(domain_model.positions) == 1
        assert domain_model.version == 2

    def test_model_dto_from_domain_conversion(self):
        """Test conversion from domain InvestmentModel to DTO."""
        from src.schemas.models import ModelDTO

        domain_model = InvestmentModel(
            model_id="507f1f77bcf86cd799439011",
            name="Domain Model",
            positions=[
                Position(
                    security_id="STOCK1234567890123456789",
                    target=TargetPercentage(Decimal("0.45")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.025"), high_drift=Decimal("0.075")
                    ),
                )
            ],
            portfolios=["683b6d88a29ee10e8b499643"],
            version=3,
        )

        model_dto = ModelDTO.from_domain(domain_model)

        assert model_dto.model_id == "507f1f77bcf86cd799439011"
        assert model_dto.name == "Domain Model"
        assert len(model_dto.positions) == 1
        assert model_dto.version == 3


@pytest.mark.unit
class TestModelPostDTO:
    """Test ModelPostDTO for model creation."""

    def test_valid_model_post_dto_creation(self):
        """Test creation of valid ModelPostDTO."""
        from src.schemas.models import ModelPositionDTO, ModelPostDTO

        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.65"),
            high_drift=Decimal("0.05"),
            low_drift=Decimal("0.03"),
        )

        model_post_dto = ModelPostDTO(
            name="New Model",
            positions=[position_dto],
            portfolios=["683b6d88a29ee10e8b499643"],
        )

        assert model_post_dto.name == "New Model"
        assert len(model_post_dto.positions) == 1
        assert len(model_post_dto.portfolios) == 1

    def test_model_post_dto_to_domain_conversion(self):
        """Test conversion from ModelPostDTO to domain for creation."""
        from src.core.mappers import ModelMapper
        from src.schemas.models import ModelPositionDTO, ModelPostDTO

        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.60"),
            high_drift=Decimal("0.05"),
            low_drift=Decimal("0.03"),
        )

        model_post_dto = ModelPostDTO(
            name="New Model",
            positions=[position_dto],
            portfolios=["683b6d88a29ee10e8b499643"],
        )

        # Use mapper instead of DTO method
        domain_model = ModelMapper.from_post_dto(model_post_dto)

        assert domain_model.name == "New Model"
        assert len(domain_model.positions) == 1
        assert domain_model.portfolios == ["683b6d88a29ee10e8b499643"]
        assert domain_model.version == 1  # Default for new models
        assert domain_model.last_rebalance_date is None
        assert domain_model.model_id is not None  # Should generate new ID


@pytest.mark.unit
class TestModelPutDTO:
    """Test ModelPutDTO for model updates."""

    def test_valid_model_put_dto_creation(self):
        """Test creation of valid ModelPutDTO."""
        from src.schemas.models import ModelPositionDTO, ModelPutDTO

        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.55"),
            high_drift=Decimal("0.04"),
            low_drift=Decimal("0.02"),
        )

        model_put_dto = ModelPutDTO(
            name="Updated Model",
            positions=[position_dto],
            portfolios=["683b6d88a29ee10e8b499643"],
            last_rebalance_date=datetime(2024, 12, 19, 15, 45, 0, tzinfo=timezone.utc),
            version=2,
        )

        assert model_put_dto.name == "Updated Model"
        assert len(model_put_dto.positions) == 1
        assert model_put_dto.version == 2

    def test_model_put_dto_to_domain_conversion_with_id(self):
        """Test conversion from ModelPutDTO to domain with ID."""
        from src.schemas.models import ModelPositionDTO, ModelPutDTO

        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.70"),
            high_drift=Decimal("0.06"),
            low_drift=Decimal("0.04"),
        )

        model_put_dto = ModelPutDTO(
            name="Updated Model",
            positions=[position_dto],
            portfolios=["683b6d88a29ee10e8b499643"],
            version=3,
        )

        domain_model = model_put_dto.to_domain("507f1f77bcf86cd799439011")

        assert str(domain_model.model_id) == "507f1f77bcf86cd799439011"
        assert domain_model.name == "Updated Model"
        assert domain_model.version == 3


@pytest.mark.unit
class TestModelPortfolioDTO:
    """Test ModelPortfolioDTO for portfolio operations."""

    def test_valid_model_portfolio_dto_creation(self):
        """Test creation of valid ModelPortfolioDTO."""
        from src.schemas.models import ModelPortfolioDTO

        portfolio_dto = ModelPortfolioDTO(
            portfolios=["683b6d88a29ee10e8b499643", "683b6d88a29ee10e8b499644"]
        )

        assert len(portfolio_dto.portfolios) == 2
        assert "683b6d88a29ee10e8b499643" in portfolio_dto.portfolios

    def test_model_portfolio_dto_validation(self):
        """Test portfolio DTO validation."""
        from src.schemas.models import ModelPortfolioDTO

        # Test empty portfolios list
        with pytest.raises(ValidationError, match="at least 1 item"):
            ModelPortfolioDTO(portfolios=[])

        # Test duplicate portfolios
        with pytest.raises(ValidationError, match="duplicate portfolio IDs"):
            ModelPortfolioDTO(portfolios=["portfolio1", "portfolio1"])


@pytest.mark.unit
class TestSchemaSerialization:
    """Test JSON serialization and deserialization."""

    def test_model_dto_json_serialization(self):
        """Test JSON serialization of ModelDTO."""
        from src.schemas.models import ModelDTO, ModelPositionDTO

        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.25"),
            high_drift=Decimal("0.05"),
            low_drift=Decimal("0.03"),
        )

        model_dto = ModelDTO(
            model_id="507f1f77bcf86cd799439011",
            name="Serialization Test",
            positions=[position_dto],
            portfolios=["683b6d88a29ee10e8b499643"],
            version=1,
        )

        json_data = model_dto.model_dump(mode='json')

        assert json_data["model_id"] == "507f1f77bcf86cd799439011"
        assert json_data["name"] == "Serialization Test"
        assert len(json_data["positions"]) == 1
        assert json_data["positions"][0]["target"] == "0.25"  # Decimal as string

    def test_model_dto_json_deserialization(self):
        """Test JSON deserialization to ModelDTO."""
        from src.schemas.models import ModelDTO

        json_data = {
            "model_id": "507f1f77bcf86cd799439011",
            "name": "Deserialization Test",
            "positions": [
                {
                    "security_id": "STOCK1234567890123456789",
                    "target": "0.30",
                    "high_drift": "0.06",
                    "low_drift": "0.04",
                }
            ],
            "portfolios": ["683b6d88a29ee10e8b499643"],
            "version": 1,
        }

        model_dto = ModelDTO(**json_data)

        assert model_dto.model_id == "507f1f77bcf86cd799439011"
        assert model_dto.name == "Deserialization Test"
        assert len(model_dto.positions) == 1
        assert model_dto.positions[0].target == Decimal("0.30")

    def test_decimal_precision_preservation(self):
        """Test that Decimal precision is preserved in serialization."""
        from src.schemas.models import ModelPositionDTO

        # Create position with valid precision (multiple of 0.005)
        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.125"),  # Valid: 0.125 = 25 * 0.005
            high_drift=Decimal("0.05"),
            low_drift=Decimal("0.03"),
        )

        # Test serialization preserves precision
        json_data = position_dto.model_dump(mode='json')
        reconstructed_dto = ModelPositionDTO(**json_data)

        assert reconstructed_dto.target == Decimal("0.125")
        assert reconstructed_dto.high_drift == Decimal("0.05")
        assert reconstructed_dto.low_drift == Decimal("0.03")
