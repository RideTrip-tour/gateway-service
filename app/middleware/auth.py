from fastapi import HTTPException, Request

from app.services.auth import validate_jwt
from config import settings


async def jwt_middleware(request: Request):
    public_paths = settings.public_paths
    if any(request.url.path.startswith(path) for path in public_paths):
        return

    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Token missing")

    user = await validate_jwt(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    request.state.user = user  # Добавляем user в запрос
