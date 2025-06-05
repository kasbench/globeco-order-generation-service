"""
Database connection and configuration for MongoDB with Beanie ODM.

This module handles MongoDB connection setup, database initialization,
and provides connection management for the application.
"""

import asyncio
import logging
from typing import List, Optional

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError

from src.config import get_settings
from src.core.exceptions import DatabaseConnectionError
from src.models.model import ModelDocument

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages MongoDB database connections and initialization."""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self._is_initialized = False

    async def connect(self) -> None:
        """
        Establish connection to MongoDB and initialize Beanie ODM.

        Raises:
            DatabaseConnectionError: If connection fails
        """
        try:
            settings = get_settings()

            # Create MongoDB client
            self.client = AsyncIOMotorClient(
                settings.database_url,
                serverSelectionTimeoutMS=settings.database_timeout_ms,
                maxPoolSize=settings.database_max_connections,
                minPoolSize=settings.database_min_connections,
                maxIdleTimeMS=settings.database_idle_timeout_ms,
            )

            # Test connection
            await self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")

            # Get database
            self.database = self.client[settings.database_name]

            # Initialize Beanie with document models
            await init_beanie(
                database=self.database,
                document_models=[ModelDocument],
            )

            self._is_initialized = True
            logger.info(
                f"Database '{settings.database_name}' initialized with Beanie ODM"
            )

        except ServerSelectionTimeoutError as e:
            error_msg = f"Failed to connect to MongoDB: {str(e)}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e
        except ConfigurationError as e:
            error_msg = f"MongoDB configuration error: {str(e)}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected database connection error: {str(e)}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e

    async def disconnect(self) -> None:
        """Close database connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            self._is_initialized = False
            logger.info("Disconnected from MongoDB")

    async def ping(self) -> bool:
        """
        Check if database connection is alive.

        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            if not self.client:
                return False
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            logger.warning(f"Database ping failed: {str(e)}")
            return False

    async def create_indexes(self) -> None:
        """Create database indexes for optimal query performance."""
        if not self._is_initialized:
            raise DatabaseConnectionError("Database not initialized")

        try:
            # Indexes are defined in the ModelDocument class and created by Beanie
            # This method can be extended for custom index creation if needed
            logger.info("Database indexes verified/created successfully")
        except Exception as e:
            error_msg = f"Failed to create database indexes: {str(e)}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e

    def get_database(self) -> AsyncIOMotorDatabase:
        """
        Get the database instance.

        Returns:
            AsyncIOMotorDatabase: The database instance

        Raises:
            DatabaseConnectionError: If database is not initialized
        """
        if not self._is_initialized or self.database is None:
            raise DatabaseConnectionError("Database not initialized")
        return self.database

    @property
    def is_connected(self) -> bool:
        """Check if database is connected and initialized."""
        return self._is_initialized and self.client is not None


# Global database manager instance
db_manager = DatabaseManager()


async def get_database() -> AsyncIOMotorDatabase:
    """
    FastAPI dependency to get database instance.

    Returns:
        AsyncIOMotorDatabase: The database instance
    """
    return db_manager.get_database()


async def init_database() -> None:
    """Initialize database connection for application startup."""
    await db_manager.connect()
    await db_manager.create_indexes()


async def close_database() -> None:
    """Close database connection for application shutdown."""
    await db_manager.disconnect()


async def health_check_database() -> bool:
    """
    Health check for database connectivity.

    Returns:
        bool: True if database is healthy, False otherwise
    """
    return await db_manager.ping()
