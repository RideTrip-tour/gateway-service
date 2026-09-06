import logging

import jwt

from config import settings

logger = logging.getLogger(__name__)


async def validate_jwt(token: str) -> dict | None:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            audience=settings.gateway_name,
            algorithms=settings.jwt_algorithm,
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Access token expired")
        return None
    except jwt.InvalidAudienceError:
        logger.warning("Invalid access token audience")
        return None
    except jwt.PyJWTError as e:
        logger.error(f"Ошибка декодирования токена: {e}")
        return None

    if data and data.get("is_active", True):
        return data

    return None
