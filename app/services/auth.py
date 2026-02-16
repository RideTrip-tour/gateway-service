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
        logger.warning(f"Токен просрочен: {token}")
        return None
    except jwt.InvalidAudienceError:
        logger.warning(f"Неверный audience для токена: {token}")
        return None
    except jwt.PyJWTError as e:
        logger.error(f"Ошибка декодирования токена: {e}")
        return None
        
    if data and data.get("is_active", False):
        logger.debug(f"Данные пользователя: {data}")
        return data

    return None
