"""
Domain Repository Interfaces.

This module exports repository interfaces that define contracts for
domain entity persistence.
"""

from src.domain.repositories.base_repository import BaseRepository
from src.domain.repositories.model_repository import ModelRepository

__all__ = [
    "BaseRepository",
    "ModelRepository",
]
