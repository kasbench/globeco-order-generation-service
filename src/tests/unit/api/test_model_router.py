"""
Tests for model management API router endpoints.

This module tests the FastAPI router for investment model operations:
- GET /models - List all models
- GET /model/{model_id} - Get specific model
- POST /models - Create new model
- PUT /model/{model_id} - Update existing model
- POST /model/{model_id}/position - Add position to model
- PUT /model/{model_id}/position - Update model position
- DELETE /model/{model_id}/position - Remove position from model
- POST /model/{model_id}/portfolio - Add portfolios to model
- DELETE /model/{model_id}/portfolio - Remove portfolios from model

Tests cover status codes, request/response validation, error scenarios, and service integration.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from src.core.exceptions import ModelNotFoundError, OptimisticLockingError
from src.core.exceptions import ValidationError as DomainValidationError
from src.domain.entities.model import InvestmentModel, Position
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage
from src.schemas.models import (
    ModelDTO,
    ModelPortfolioDTO,
    ModelPositionDTO,
    ModelPostDTO,
    ModelPutDTO,
)


@pytest.fixture
def mock_model_service():
    """Mock model service for testing."""
    return AsyncMock()


@pytest.fixture
def sample_model_dto():
    """Sample ModelDTO for testing."""
    return ModelDTO(
        model_id="507f1f77bcf86cd799439011",
        name="Test Investment Model",
        positions=[
            ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("0.60"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            )
        ],
        portfolios=["683b6d88a29ee10e8b499643"],
        last_rebalance_date=datetime(2024, 12, 19, 10, 30, 0, tzinfo=timezone.utc),
        version=1,
    )


@pytest.fixture
def sample_position_dto():
    """Sample ModelPositionDTO for testing."""
    return ModelPositionDTO(
        security_id="BOND1111111111111111111A",
        target=Decimal("0.30"),
        high_drift=Decimal("0.02"),
        low_drift=Decimal("0.02"),
    )


@pytest.fixture
def app_client():
    """Create a test client with the full app for dependency injection."""
    from src.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.mark.unit
class TestGetModelsEndpoint:
    """Test GET /models endpoint."""

    def test_get_models_success(self, app_client, sample_model_dto):
        """Test successful retrieval of all models."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_all_models.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data) == 1
        assert response_data[0]["model_id"] == "507f1f77bcf86cd799439011"
        assert response_data[0]["name"] == "Test Investment Model"

        mock_service.get_all_models.assert_called_once()

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_empty_list(self, app_client):
        """Test retrieval when no models exist."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_all_models.return_value = []

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_service_error(self, app_client):
        """Test handling of service errors during model retrieval."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_all_models.side_effect = Exception("Database connection error")

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models")

        # Verify
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestGetModelsWithPaginationEndpoint:
    """Test GET /models endpoint with pagination and sorting."""

    def test_get_models_with_pagination_offset_only(self, app_client, sample_model_dto):
        """Test pagination with offset only."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?offset=5")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_models_with_pagination.assert_called_once_with(
            offset=5, limit=None, sort_by=None
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_with_pagination_limit_only(self, app_client, sample_model_dto):
        """Test pagination with limit only."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?limit=10")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_models_with_pagination.assert_called_once_with(
            offset=None, limit=10, sort_by=None
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_with_pagination_offset_and_limit(
        self, app_client, sample_model_dto
    ):
        """Test pagination with both offset and limit."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?offset=5&limit=10")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_models_with_pagination.assert_called_once_with(
            offset=5, limit=10, sort_by=None
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_with_sorting_single_field(self, app_client, sample_model_dto):
        """Test sorting by single field."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?sort_by=name")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_models_with_pagination.assert_called_once_with(
            offset=None, limit=None, sort_by=["name"]
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_with_sorting_multiple_fields(
        self, app_client, sample_model_dto
    ):
        """Test sorting by multiple fields."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?sort_by=name,last_rebalance_date")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_models_with_pagination.assert_called_once_with(
            offset=None, limit=None, sort_by=["name", "last_rebalance_date"]
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_with_pagination_and_sorting(self, app_client, sample_model_dto):
        """Test pagination with sorting."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get(
            "/api/v1/models?offset=5&limit=10&sort_by=model_id,name"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_models_with_pagination.assert_called_once_with(
            offset=5, limit=10, sort_by=["model_id", "name"]
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_offset_greater_than_count_fallback(self, app_client):
        """Test offset greater than number of rows returns empty list."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.return_value = []

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?offset=1000")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_negative_offset_error(self, app_client):
        """Test negative offset returns 400 error."""
        # Setup
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?offset=-1")

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "Offset must be a non-negative integer" in response_data["detail"]

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_negative_limit_error(self, app_client):
        """Test negative limit returns 400 error."""
        # Setup
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?limit=-1")

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "Limit must be a non-negative integer" in response_data["detail"]

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_invalid_sort_field_error(self, app_client):
        """Test invalid sort field returns 400 error."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.side_effect = DomainValidationError(
            "Invalid sort field: invalid_field. Valid fields are: model_id, name, last_rebalance_date"
        )

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?sort_by=invalid_field")

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "Invalid sort field" in response_data["detail"]

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_empty_sort_by_ignored(self, app_client, sample_model_dto):
        """Test empty sort_by parameter falls back to original method."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_all_models.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?sort_by=")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_all_models.assert_called_once()

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_sort_by_with_spaces(self, app_client, sample_model_dto):
        """Test sort_by parameter handles spaces correctly."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?sort_by=name, last_rebalance_date")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_models_with_pagination.assert_called_once_with(
            offset=None, limit=None, sort_by=["name", "last_rebalance_date"]
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_zero_offset_and_limit(self, app_client, sample_model_dto):
        """Test zero offset and limit are valid."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_models_with_pagination.return_value = []

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models?offset=0&limit=0")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_models_with_pagination.assert_called_once_with(
            offset=0, limit=0, sort_by=None
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_models_fallback_to_original_method(self, app_client, sample_model_dto):
        """Test that when no pagination/sorting parameters are provided, original method is used."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_all_models.return_value = [sample_model_dto]

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_all_models.assert_called_once()
        # Should NOT call pagination method
        mock_service.get_models_with_pagination.assert_not_called()

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestGetModelByIdEndpoint:
    """Test GET /model/{model_id} endpoint."""

    def test_get_model_by_id_success(self, app_client, sample_model_dto):
        """Test successful retrieval of model by ID."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_model_by_id.return_value = sample_model_dto

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/model/507f1f77bcf86cd799439011")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data["model_id"] == "507f1f77bcf86cd799439011"
        assert response_data["name"] == "Test Investment Model"

        mock_service.get_model_by_id.assert_called_once_with("507f1f77bcf86cd799439011")

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_model_by_id_not_found(self, app_client):
        """Test model not found scenario."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_model_by_id.side_effect = ModelNotFoundError("Model not found")

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/model/507f1f77bcf86cd799439011")

        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_model_by_id_invalid_format(self, app_client):
        """Test invalid model ID format."""
        # Setup - need to override dependencies even for validation errors
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/model/invalid_id")

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestCreateModelEndpoint:
    """Test POST /models endpoint."""

    def test_create_model_success(self, app_client, sample_model_dto):
        """Test successful model creation."""
        # Setup
        mock_service = AsyncMock()
        mock_service.create_model.return_value = sample_model_dto

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {
            "name": "Test Investment Model",
            "positions": [
                {
                    "security_id": "STOCK1234567890123456789",
                    "target": "0.60",
                    "high_drift": "0.05",
                    "low_drift": "0.03",
                }
            ],
            "portfolios": ["683b6d88a29ee10e8b499643"],
        }

        # Execute
        response = app_client.post("/api/v1/models", json=request_data)

        # Verify
        assert response.status_code == status.HTTP_201_CREATED

        response_data = response.json()
        assert response_data["name"] == "Test Investment Model"
        assert len(response_data["positions"]) == 1

        mock_service.create_model.assert_called_once()

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_create_model_validation_error(self, app_client):
        """Test model creation with validation errors."""
        # Setup - need to override dependencies even for validation errors
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Invalid request data - target sum > 0.95
        request_data = {
            "name": "Invalid Model",
            "positions": [
                {
                    "security_id": "STOCK1234567890123456789",
                    "target": "0.50",  # Valid individual target
                    "high_drift": "0.05",
                    "low_drift": "0.03",
                },
                {
                    "security_id": "BOND1111111111111111111A",
                    "target": "0.50",  # Valid individual target
                    "high_drift": "0.05",
                    "low_drift": "0.03",
                },
                # Sum = 1.00 > 0.95, should trigger business validation error
            ],
            "portfolios": ["683b6d88a29ee10e8b499643"],
        }

        # Execute
        response = app_client.post("/api/v1/models", json=request_data)

        # Verify - Pydantic validation errors return 422 (Unprocessable Entity)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_create_model_domain_validation_error(self, app_client):
        """Test domain validation error during model creation."""
        # Setup
        mock_service = AsyncMock()
        mock_service.create_model.side_effect = DomainValidationError(
            "Invalid business rule"
        )

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {
            "name": "Test Model",
            "positions": [],
            "portfolios": ["683b6d88a29ee10e8b499643"],
        }

        # Execute
        response = app_client.post("/api/v1/models", json=request_data)

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestUpdateModelEndpoint:
    """Test PUT /model/{model_id} endpoint."""

    def test_update_model_success(self, app_client, sample_model_dto):
        """Test successful model update."""
        # Setup
        updated_model = sample_model_dto.model_copy()
        updated_model.name = "Updated Model Name"
        updated_model.version = 2

        mock_service = AsyncMock()
        mock_service.update_model.return_value = updated_model

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {
            "name": "Updated Model Name",
            "positions": [
                {
                    "security_id": "STOCK1234567890123456789",
                    "target": "0.60",
                    "high_drift": "0.05",
                    "low_drift": "0.03",
                }
            ],
            "portfolios": ["683b6d88a29ee10e8b499643"],
            "version": 1,
        }

        # Execute
        response = app_client.put(
            "/api/v1/model/507f1f77bcf86cd799439011", json=request_data
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data["name"] == "Updated Model Name"
        assert response_data["version"] == 2

        mock_service.update_model.assert_called_once()

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_update_model_not_found(self, app_client):
        """Test update of non-existent model."""
        # Setup
        mock_service = AsyncMock()
        mock_service.update_model.side_effect = ModelNotFoundError("Model not found")

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {
            "name": "Updated Model",
            "positions": [],
            "portfolios": ["683b6d88a29ee10e8b499643"],
            "version": 1,
        }

        # Execute
        response = app_client.put(
            "/api/v1/model/507f1f77bcf86cd799439011", json=request_data
        )

        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_update_model_optimistic_locking_error(self, app_client):
        """Test optimistic locking conflict during update."""
        # Setup
        mock_service = AsyncMock()
        mock_service.update_model.side_effect = OptimisticLockingError(
            "Version conflict"
        )

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {
            "name": "Updated Model",
            "positions": [],
            "portfolios": ["683b6d88a29ee10e8b499643"],
            "version": 1,  # Outdated version
        }

        # Execute
        response = app_client.put(
            "/api/v1/model/507f1f77bcf86cd799439011", json=request_data
        )

        # Verify
        assert response.status_code == status.HTTP_409_CONFLICT

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPositionManagementEndpoints:
    """Test position management endpoints."""

    def test_add_position_success(
        self, app_client, sample_model_dto, sample_position_dto
    ):
        """Test successful position addition."""
        # Setup
        updated_model = sample_model_dto.model_copy()
        updated_model.positions.append(sample_position_dto)

        mock_service = AsyncMock()
        mock_service.add_position.return_value = updated_model

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {
            "security_id": "BOND1111111111111111111A",
            "target": "0.30",
            "high_drift": "0.02",
            "low_drift": "0.02",
        }

        # Execute
        response = app_client.post(
            "/api/v1/model/507f1f77bcf86cd799439011/position", json=request_data
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data["positions"]) == 2

        mock_service.add_position.assert_called_once()

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_update_position_success(self, app_client, sample_model_dto):
        """Test successful position update."""
        # Setup
        mock_service = AsyncMock()
        mock_service.update_position.return_value = sample_model_dto

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {
            "security_id": "STOCK1234567890123456789",
            "target": "0.65",  # Updated target
            "high_drift": "0.05",
            "low_drift": "0.03",
        }

        # Execute
        response = app_client.put(
            "/api/v1/model/507f1f77bcf86cd799439011/position", json=request_data
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.update_position.assert_called_once()

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_remove_position_success(self, app_client, sample_model_dto):
        """Test successful position removal."""
        # Setup
        updated_model = sample_model_dto.model_copy()
        updated_model.positions = []  # Position removed

        mock_service = AsyncMock()
        mock_service.remove_position.return_value = updated_model

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {
            "security_id": "STOCK1234567890123456789",
            "target": "0.60",
            "high_drift": "0.05",
            "low_drift": "0.03",
        }

        # Execute - Use request() method for DELETE with body data
        response = app_client.request(
            "DELETE",
            "/api/v1/model/507f1f77bcf86cd799439011/position",
            json=request_data,
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data["positions"]) == 0

        mock_service.remove_position.assert_called_once()

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPortfolioAssociationEndpoints:
    """Test portfolio association endpoints."""

    def test_add_portfolios_success(self, app_client, sample_model_dto):
        """Test successful portfolio addition."""
        # Setup
        updated_model = sample_model_dto.model_copy()
        updated_model.portfolios.append("683b6d88a29ee10e8b499644")

        mock_service = AsyncMock()
        mock_service.add_portfolios.return_value = updated_model

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {"portfolios": ["683b6d88a29ee10e8b499644"]}

        # Execute
        response = app_client.post(
            "/api/v1/model/507f1f77bcf86cd799439011/portfolio", json=request_data
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data["portfolios"]) == 2

        mock_service.add_portfolios.assert_called_once()

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_remove_portfolios_success(self, app_client, sample_model_dto):
        """Test successful portfolio removal."""
        # Setup
        updated_model = sample_model_dto.model_copy()
        updated_model.portfolios = []  # All portfolios removed

        mock_service = AsyncMock()
        mock_service.remove_portfolios.return_value = updated_model

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {"portfolios": ["683b6d88a29ee10e8b499643"]}

        # Execute - Use request() method for DELETE with body data
        response = app_client.request(
            "DELETE",
            "/api/v1/model/507f1f77bcf86cd799439011/portfolio",
            json=request_data,
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_service.remove_portfolios.assert_called_once()

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_remove_portfolios_validation_error(self, app_client):
        """Test portfolio removal with validation error (cannot remove all portfolios)."""
        # Setup
        mock_service = AsyncMock()
        mock_service.remove_portfolios.side_effect = DomainValidationError(
            "Cannot remove all portfolios from model"
        )

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        request_data = {"portfolios": ["683b6d88a29ee10e8b499643"]}

        # Execute - Use request() method for DELETE with body data
        response = app_client.request(
            "DELETE",
            "/api/v1/model/507f1f77bcf86cd799439011/portfolio",
            json=request_data,
        )

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestModelRouterErrorHandling:
    """Test error handling scenarios across all endpoints."""

    def test_internal_server_error_handling(self, app_client):
        """Test handling of unexpected internal errors."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_all_models.side_effect = Exception("Unexpected error")

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Execute
        response = app_client.get("/api/v1/models")

        # Verify
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_request_validation_errors(self, app_client):
        """Test Pydantic request validation errors."""
        # Setup - need to override dependencies even for validation errors
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.models import get_model_service

        app_client.app.dependency_overrides[get_model_service] = lambda: mock_service

        # Invalid request body (missing required fields)
        invalid_request = {
            "name": "",  # Empty name
            "portfolios": [],  # Empty portfolios
        }

        # Execute
        response = app_client.post("/api/v1/models", json=invalid_request)

        # Verify - Pydantic validation errors return 422 (Unprocessable Entity)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_json_decode_error_handling(self, app_client):
        """Test handling of malformed JSON requests."""
        # Execute with invalid JSON
        response = app_client.post(
            "/api/v1/models",
            data="invalid json content",
            headers={"Content-Type": "application/json"},
        )

        # Verify
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
