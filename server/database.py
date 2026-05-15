from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

# Lazy singleton
_mongo_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None
_db_available: bool | None = None


def get_mongo_url() -> str:
    # Prefer env var; deepresearch Config also reads MONGO_URL
    return os.getenv("MONGO_URL", "mongodb://localhost:27017/deepresearch")


def get_db() -> AsyncIOMotorDatabase | None:
    """Return the MongoDB database handle, or None if unavailable."""
    global _mongo_client, _db, _db_available
    if _db_available is False:
        return None
    if _db is None:
        url = get_mongo_url()
        try:
            _mongo_client = AsyncIOMotorClient(
                url,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
            )
            db_name = url.rsplit("/", 1)[-1].split("?")[0] or "deepresearch"
            _db = _mongo_client[db_name]
            _db_available = True
            logger.info("MongoDB connected: %s", url.replace(_extract_password(url), "***"))
        except ServerSelectionTimeoutError as exc:
            _db_available = False
            logger.error(
                "MongoDB connection failed. "
                "Check MONGO_URL, network access, and Atlas cluster status. Error: %s",
                exc,
            )
            return None
    return _db


def _extract_password(url: str) -> str:
    """Redact password from MongoDB URL for safe logging."""
    if "@" in url:
        prefix = url.split("@", 1)[0]
        if ":" in prefix:
            return prefix.rsplit(":", 1)[-1]
    return ""


async def close_mongo() -> None:
    global _mongo_client, _db_available
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        _db = None
        _db_available = None


# Collection helpers

def jobs_collection() -> Any | None:
    db = get_db()
    return db["jobs"] if db is not None else None


def reports_collection() -> Any | None:
    db = get_db()
    return db["reports"] if db is not None else None
