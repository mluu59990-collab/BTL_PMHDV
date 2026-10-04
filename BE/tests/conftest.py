"""Each run creates a random MySQL database and drops only that database."""

import asyncio
import os
import secrets
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from app.infrastructure.db.bootstrap import apply_sql


@pytest.fixture(scope="session")
def client():
    maintenance = os.getenv("TEST_DATABASE_URL")
    if not maintenance:
        pytest.skip(
            "Set TEST_DATABASE_URL to a MySQL URL with CREATE DATABASE permission"
        )
    base_url = make_url(maintenance).set(drivername="mysql+asyncmy", database="")
    database_name = "cms_test_" + uuid.uuid4().hex
    test_url = base_url.set(database=database_name)

    async def prepare():
        admin = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
        try:
            async with admin.connect() as conn:
                await conn.exec_driver_sql(
                    f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
        finally:
            await admin.dispose()
        engine = create_async_engine(test_url)
        try:
            await apply_sql(engine, dev_users=True)
            await apply_sql(engine, dev_users=True)  # repeat migration and seed safety
        finally:
            await engine.dispose()

    async def cleanup():
        admin = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
        try:
            async with admin.connect() as conn:
                await conn.exec_driver_sql(f"DROP DATABASE IF EXISTS `{database_name}`")
        finally:
            await admin.dispose()

    try:
        asyncio.run(prepare())
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("DATABASE_URL", test_url.render_as_string(hide_password=False))
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
