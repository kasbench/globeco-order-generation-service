"""
Database infrastructure package.

This package provides MongoDB database connection and repository implementations
using Beanie ODM for the Order Generation Service.
"""

from .database import (
    DatabaseManager,
    close_database,
    db_manager,
    get_database,
    health_check_database,
    init_database,
)
from .repositories import MongoModelRepository

__all__ = [
    "DatabaseManager",
    "db_manager",
    "get_database",
    "init_database",
    "close_database",
    "health_check_database",
    "MongoModelRepository",
]
