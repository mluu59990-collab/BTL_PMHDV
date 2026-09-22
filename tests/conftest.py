"""Integration tests use a disposable database, never the application's database.

TEST_DATABASE_URL must point to a PostgreSQL maintenance database whose user has
CREATEDB permission. Each run creates and drops its own cms_test_<uuid> database.
"""

import asyncio
import os
import secrets
import uuid
from pathlib import Path

import asyncpg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def client():
    maintenance = os.getenv("TEST_DATABASE_URL")
    if not maintenance:
        pytest.skip(
            "Set TEST_DATABASE_URL to a PostgreSQL database with CREATEDB permission"
        )
    base_url = make_url(maintenance).set(drivername="postgresql")
    database_name = "cms_test_" + uuid.uuid4().hex
    test_url = base_url.set(database=database_name)

    async def prepare():
        conn = await asyncpg.connect(base_url.render_as_string(hide_password=False))
        try:
            await conn.execute(f'CREATE DATABASE "{database_name}"')
        finally:
            await conn.close()
        conn = await asyncpg.connect(test_url.render_as_string(hide_password=False))
        try:
            for path in sorted((ROOT / "sql").glob("*.sql")):
                await conn.execute(path.read_text())
            # Verify that incremental migrations and seeds can be applied twice.
            for name in ("04_catalog_schema.sql", "05_catalog_seed.sql"):
                await conn.execute((ROOT / "sql" / name).read_text())
        finally:
            await conn.close()

    async def cleanup():
        conn = await asyncpg.connect(base_url.render_as_string(hide_password=False))
        try:
            await conn.execute(
                f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'
            )
        finally:
            await conn.close()

    try:
        asyncio.run(prepare())
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv(
                "DATABASE_URL",
                test_url.set(drivername="postgresql+asyncpg").render_as_string(
                    hide_password=False
                ),
            )
            patch.setenv("JWT_SECRET_KEY", secrets.token_urlsafe(48))
            patch.setenv("DEBUG", "false")
            from app.main import app

            with TestClient(app) as test_client:
                yield test_client
    finally:
        asyncio.run(cleanup())


@pytest.fixture(scope="session")
def headers(client):
    result = {}
    for username in ("admin", "sale01", "muahang01", "kho01", "ketoan01", "khach01"):
        password = "Admin@123456" if username == "admin" else "Test@123456"
        response = client.post(
            "/api/v1/auth/login", data={"username": username, "password": password}
        )
        assert response.status_code == 200, response.text
        result[username] = {
            "Authorization": "Bearer " + response.json()["access_token"]
        }
    return result
