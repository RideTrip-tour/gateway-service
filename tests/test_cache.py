import json
from unittest.mock import AsyncMock

import pytest

from app.services.cache import cache_jwt, get_cached_jwt, redis_client
from config import settings


@pytest.mark.asyncio
async def test_get_cached_jwt_return_jwt(mocker):
    """Тест успешного получения JWT из кэша."""
    token = "test_token"
    token_key = f"jwt:{token}"
    data = {"user_id": 123, "valid": True}
    mock_redis = mocker.patch.object(
        redis_client, "get", AsyncMock(return_value=json.dumps(data))
    )
    result = await get_cached_jwt(token)
    assert result == data
    mock_redis.assert_called_once_with(token_key)


@pytest.mark.asyncio
async def test_get_cached_jwt_return_none(mocker):
    """Тест успешного получения JWT из кэша."""
    token = "test_token"
    token_key = f"jwt:{token}"
    mock_redis = mocker.patch.object(redis_client, "get", AsyncMock(return_value=None))
    result = await get_cached_jwt(token)
    assert result is None
    mock_redis.assert_called_once_with(token_key)


@pytest.mark.asyncio
async def test_cache_jwt_success(mocker):
    """Тест успешного сохранения JWT в кэш."""
    token = "test_token"
    data = {"user_id": 123, "valid": True}
    mock_redis = mocker.patch.object(redis_client, "setex", AsyncMock())
    await cache_jwt(token, data)
    json_data = json.dumps(data)
    token_key = f"jwt:{token}"
    mock_redis.assert_called_once_with(token_key, settings.redis_ttl, json_data)
