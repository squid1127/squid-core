"""(Actual) Memory Management System for SquidCore, uses Redis and MongoDB for storage."""

import redis.asyncio as redis
import motor.motor_asyncio
from urllib.parse import urlparse, urlunparse

import os

import logging

logger = logging.getLogger("core.memory")

def sanitize_url(url: str) -> str:
    """
    Sanitize a URL by removing sensitive credentials from it.
    
    Args:
        url (str): The URL to sanitize.
        
    Returns:
        str: The sanitized URL with credentials masked.
    """
    if not url:
        return url
    
    try:
        parsed = urlparse(url)
        # If there's a password, mask it
        if parsed.password:
            # Replace password with asterisks
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
        else:
            netloc = parsed.netloc
        
        # Reconstruct URL without exposing credentials
        sanitized = urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        return sanitized
    except Exception:
        # If URL parsing fails, return a generic message
        return "[URL sanitization failed]"

class InitError(Exception):
    """Custom exception for initialization errors in the Memory Manager."""
    pass


class Memory:
    """
    Memory Manager for SquidCore, handles Redis and MongoDB connections.
    
    Attributes:
        redis (redis.Redis): Redis client for caching and storage.
        mongo (motor.motor_asyncio.AsyncIOMotorClient): MongoDB client for database operations.
        redis_enabled (bool): Flag to indicate if Redis is enabled.
        mongo_enabled (bool): Flag to indicate if MongoDB is enabled.
    Args:
        redis (bool): Whether to enable Redis connection.
        mongo (bool): Whether to enable MongoDB connection.
        from_env (bool): Whether to load Redis and MongoDB configurations from environment variables.
    """

    def __init__(self, redis: bool = False, mongo: bool = False, from_env: bool = True):
        """Initialize the Memory Manager with Redis and MongoDB connections."""
        # Redis and MongoDB objects
        self.redis = None
        self.mongo = None
        self.mongo_db = None
        
        self.redis_enabled = redis
        self.mongo_enabled = mongo
        
        if not from_env:
            raise NotImplementedError("Currently, only environment variable loading is supported.")
        
    async def init(self):
        """Initialize Redis and MongoDB connections."""
        # Connect to Redis
        if self.redis_enabled:
            redis_url = os.getenv("REDIS_URL", None)
            if not redis_url:
                redis_host = os.getenv("REDIS_HOST", None)
                redis_port = os.getenv("REDIS_PORT", None)
                redis_username = os.getenv("REDIS_USERNAME", None)
                redis_password = os.getenv("REDIS_PASSWORD", None)
                if not redis_host or not redis_port:
                    raise InitError("Redis host and port must be provided if REDIS_URL is not set. Use environment variables REDIS_HOST, REDIS_PORT, REDIS_USERNAME (optional), and REDIS_PASSWORD (optional).")
                
                self.redis = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    username=redis_username,
                    password=redis_password,
                    decode_responses=True
                )
            else:
                self.redis = redis.from_url(redis_url)
            logger.info(f"Connected to Redis at {sanitize_url(redis_url)}")
            
            # Test Redis connection
            try:
                await self.redis.ping()
                logger.info("Redis connection successful")
            except redis.ConnectionError as e:
                logger.error(f"Redis connection failed: {e}")
                raise InitError("Redis connection failed")

        if self.mongo_enabled:
            mongo_url = os.getenv("MONGO_URL", None)
            if not mongo_url:
                raise InitError("MongoDB URL must be provided. Use environment variable MONGO_URL.")
            self.mongo = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
            self.mongo_db = self.mongo.get_default_database()
            logger.info(f"Connected to MongoDB at {sanitize_url(mongo_url)}")

            # Test MongoDB connection
            try:
                await self.mongo.admin.command("ping")
                logger.info("MongoDB connection successful")
            except Exception as e:
                logger.error(f"MongoDB connection failed: {e}")
                raise InitError("MongoDB connection failed")
            
        if not self.redis_enabled and not self.mongo_enabled:
            logger.warning("No memory management system enabled. Please enable Redis or MongoDB.")
            raise InitError("No memory management system enabled. Please enable Redis or MongoDB.")