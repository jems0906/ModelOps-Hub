import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Ensure app imports bind to the test database before modules are loaded.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.db import Base, SessionLocal, engine
from app.main import app
from app.core import cache
from app.routers import dashboard
from app.seed import seed_users


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


fake_redis = FakeRedis()
dashboard.async_redis_client = fake_redis
cache.sync_redis_client = fake_redis


@pytest.fixture(autouse=True)
def reset_db() -> None:
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_users(db)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_fake_redis() -> None:
    fake_redis.clear()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
