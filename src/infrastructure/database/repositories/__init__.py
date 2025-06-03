"""
Database repository implementations package.

This package contains concrete implementations of repository interfaces
using MongoDB with Beanie ODM for data persistence.
"""

from .model_repository import MongoModelRepository

__all__ = [
    "MongoModelRepository",
]
