import logging

from fastapi import HTTPException, Request

from app.services.auth import validate_jwt
from config import settings

logger = logging.getLogger(__name__)


async def jwt_middleware(request: Request):
    """Middleware для проверки JWT токена."""
    public_paths = settings.public_paths
    if any(request.url.path.startswith(path) for path in public_paths):
        return

    if request.url.path.endswith(("openapi.json", "docs", "redoc")):
        return

    access_token = request.cookies.get("access_token")
    logger.info(f"access_token: {access_token}")
    if not access_token:
        raise HTTPException(status_code=401, detail=f"Token missing {request.url.path}")

    user_data = await validate_jwt(access_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    request.state.user_data = user_data  # Добавляем user в запрос
