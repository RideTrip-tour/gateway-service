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

    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail=f"Token missing {request.url.path}")

    user = await validate_jwt(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    request.state.user = user  # Добавляем user в запрос
