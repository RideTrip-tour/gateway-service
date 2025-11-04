import httpx

from app.services.cache import cache_jwt, get_cached_jwt
from config import settings


async def validate_jwt(token: str) -> dict | None:
    # Проверка кэша
    if cached := await get_cached_jwt(token):
        return cached

    # Запрос к auth-service
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.service_map['auth']}/validate", json={"token": token}
        )

    if response.status_code == 200:
        data = response.json()
        await cache_jwt(token, data)
        return data

    return None
