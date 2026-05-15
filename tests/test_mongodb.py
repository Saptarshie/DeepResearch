"""MongoDB connectivity and diagnostic tests."""

import os
import socket

import pytest
from pymongo.errors import ServerSelectionTimeoutError

# Skip all tests in this module if MONGO_URL is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("MONGO_URL"),
    reason="MONGO_URL not set in environment",
)


class TestMongoDBConnectivity:
    """Diagnostic tests for MongoDB Atlas connection issues."""

    def test_dns_resolution(self):
        """Verify that MongoDB Atlas hostnames can be resolved via DNS.

        A failure here indicates a network/DNS issue (firewall, no internet,
        or the cluster URI is stale), NOT an authentication or code issue.
        """
        mongo_url = os.environ["MONGO_URL"]
        # Extract hostnames from mongodb+srv URI
        # e.g., mongodb+srv://user:pass@cluster0.kgyfkai.mongodb.net/...
        from urllib.parse import urlparse

        parsed = urlparse(mongo_url)
        hostname = parsed.hostname
        assert hostname, f"Could not parse hostname from MONGO_URL: {mongo_url}"

        # Try to resolve the seed hostname (SRV record lookup is done by pymongo)
        try:
            socket.getaddrinfo(hostname, None)
        except socket.gaierror as exc:
            pytest.fail(
                f"DNS resolution failed for '{hostname}'.\n"
                f"Error: {exc}\n\n"
                f"This is a network/DNS issue, not a code issue.\n"
                f"Common causes:\n"
                f"  1. No internet connection\n"
                f"  2. Corporate firewall blocking external DNS\n"
                f"  3. MongoDB Atlas cluster is paused/deleted\n"
                f"  4. SRV URI is stale/wrong\n"
            )

    def test_mongodb_connection(self):
        """Attempt a real connection to MongoDB.

        Uses a short timeout so the test fails fast rather than hanging.
        """
        import asyncio

        from motor.motor_asyncio import AsyncIOMotorClient

        mongo_url = os.environ["MONGO_URL"]
        # Short timeout for tests — fail fast
        client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
        )

        async def _check() -> None:
            result = await client.admin.command("ismaster")
            assert result.get("ok") == 1, "MongoDB ismaster command failed"

        try:
            asyncio.run(_check())
        except ServerSelectionTimeoutError as exc:
            pytest.fail(
                f"Could not connect to MongoDB.\n"
                f"Error: {exc}\n\n"
                f"Please verify:\n"
                f"  1. MONGO_URL is correct and the cluster is active\n"
                f"  2. Your IP is whitelisted in MongoDB Atlas Network Access\n"
                f"  3. Username/password in the URI are correct\n"
                f"  4. No firewall/VPN is blocking port 27017\n"
            )
        finally:
            client.close()

    def test_database_list_collections(self):
        """Verify we can list collections in the target database."""
        import asyncio

        from motor.motor_asyncio import AsyncIOMotorClient

        mongo_url = os.environ["MONGO_URL"]
        client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
        )

        async def _check() -> None:
            db_name = "deepresearch"
            db = client[db_name]
            collections = await db.list_collection_names()
            assert isinstance(collections, list)

        try:
            asyncio.run(_check())
        except ServerSelectionTimeoutError as exc:
            pytest.fail(f"Could not list collections: {exc}")
        finally:
            client.close()

    def test_env_mongo_url_parses(self):
        """Sanity check that MONGO_URL looks like a valid MongoDB URI."""
        mongo_url = os.environ["MONGO_URL"]
        assert mongo_url.startswith(("mongodb://", "mongodb+srv://")), (
            f"MONGO_URL does not start with 'mongodb://' or 'mongodb+srv://'.\n"
            f"Value: {mongo_url[:50]}..."
        )
        assert "@" in mongo_url, (
            "MONGO_URL missing '@' — check that username/password are included."
        )
