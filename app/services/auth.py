import logging

import jwt

from config import settings

logger = logging.getLogger(__name__)


async def validate_jwt(token: str) -> dict | None:

    data = jwt.decode(
        token,
        settings.jwt_secret,
        audience=settings.gateway_name,
        algorithms=settings.jwt_algorithm,
    )
    if data and data.get("is_active", False):
        logger.debug(f"Данные пользователя: {data}")
        return data

    return None
