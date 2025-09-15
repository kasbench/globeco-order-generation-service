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
from src.models.rebalance import RebalanceDocument

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages MongoDB database connections and initialization."""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self._is_initialized = False
        self._initialization_in_progress = False

    async def connect(self) -> None:
        """
        Establish connection to MongoDB and initialize Beanie ODM.

        Raises:
            DatabaseConnectionError: If connection fails
        """
        # Prevent multiple concurrent initialization attempts
        if self._initialization_in_progress:
            logger.info("Database initialization already in progress, waiting...")
            # Wait for initialization to complete
            while self._initialization_in_progress and not self._is_initialized:
                await asyncio.sleep(0.1)
            return

        if self._is_initialized:
            logger.debug("Database already initialized")
            return

        self._initialization_in_progress = True
        try:
            settings = get_settings()
            logger.info("Starting database initialization...")

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
            logger.info("Initializing Beanie ODM...")
            await init_beanie(
                database=self.database,
                document_models=[ModelDocument, RebalanceDocument],
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
        finally:
            self._initialization_in_progress = False

    async def disconnect(self) -> None:
        """Close database connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            self._is_initialized = False
            self._initialization_in_progress = False
            logger.info("Disconnected from MongoDB")

    async def ping(self) -> bool:
        """
        Check if database connection is alive.

        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            if not self.client:
                logger.debug("Database ping failed: No client connection")
                return False

            # If initialization is in progress, wait a bit and try again
            if self._initialization_in_progress:
                logger.debug("Database initialization in progress, waiting...")
                await asyncio.sleep(0.5)
                if not self._is_initialized:
                    logger.debug(
                        "Database ping failed: Initialization still in progress"
                    )
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

    @property
    def is_initializing(self) -> bool:
        """Check if database initialization is in progress."""
        return self._initialization_in_progress


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
    # If initialization is in progress, consider it healthy (starting up)
    if db_manager.is_initializing:
        logger.debug("Database health check: initialization in progress")
        return True

    # If not initialized and not initializing, it's unhealthy
    if not db_manager.is_connected:
        logger.debug("Database health check: not connected")
        return False

    return await db_manager.ping()
