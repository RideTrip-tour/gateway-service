import json
import logging

import redis.asyncio as redis

from config import settings

redis_client = redis.Redis.from_url(settings.redis_url)

DEFAULT_TTL = settings.redis_ttl

logger = logging.getLogger(__name__)


async def get_cached_jwt(token: str) -> dict | None:
    try:
        cached_data = await redis_client.get(f"jwt:{token}")
        if cached_data:
            return json.loads(cached_data)
    except Exception as ex:
        logger.error(f"Ошибка при получении токена из кеша: {ex}")
    return None


async def cache_jwt(token: str, jwt_payload: dict, ttl: int = DEFAULT_TTL):
    try:
        serialized_data = json.dumps(jwt_payload)
        await redis_client.setex(f"jwt:{token}", ttl, serialized_data)
    except Exception as ex:
        logger.error(f"Ошибка при попытке кеширования токена: {ex}")
