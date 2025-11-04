import pytest
import fakeredis.aioredis
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


from main import app


@pytest.fixture(scope="session", autouse=True)
def mock_redis():
    """
    Заменяет реальный клиент Redis на fakeredis для всех тестов.
    `autouse=True` и `scope="session"` гарантируют, что это произойдет
    один раз перед запуском всех тестов.
    """
    fake_redis_client = fakeredis.aioredis.FakeRedis()
    with patch("redis.asyncio.Redis.from_url", return_value=fake_redis_client), patch(
        "redis.asyncio.Redis.script_load",
        new=AsyncMock(return_value="e162a7a3c31d0e55a71c7242a362ad53574a4251"),
    ):
        yield


@pytest.fixture()
def client() -> TestClient:
    """Предоставляет тестовый клиент, отключая lifespan"""
    with TestClient(app, backend_options={"lifespan": "off"}) as test_client:

        yield test_client
