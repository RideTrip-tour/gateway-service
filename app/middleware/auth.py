import logging

from fastapi import HTTPException, Request

from app.services.auth import validate_jwt
from app.utils.auth_service import validate_admin_permission
from app.utils.auth_user import check_public_path
from app.utils.token import match_tokens
from config import settings

logger = logging.getLogger(__name__)


async def parse_service_request(request: Request) -> tuple[dict, str]:
    """
    Проверяет достоверность токена сервиса.
    """
    service_id = request.headers.get("X-Service-ID")
    user_context = request.headers.get("X-User-Context")
    service_token = request.headers.get("X-Service-Token")

    if not all(
        [
            service_id,
            user_context,
            service_token,
        ]
    ):
        return {}, ""

    expected_service_token = settings.service_tokens.get(service_id)

    if not await match_tokens(expected_service_token, service_token):
        raise HTTPException(status_code=401, detail="Invalid service authentication")

    if service_id == "admin":
        await validate_admin_permission(request)

    user_data = await validate_jwt(user_context)

    if not user_data:
        return {}, ""

    return user_data, service_id


async def parse_request(request: Request) -> tuple[dict, str]:
    """
    Парсит запрос на данные пользователя и тип.
    Запрос может быть:
    - user: источник - браузер, несет в себе cookie c access токеном
    - <name>_service: источник - внутренний сервис,
    """
    user_data: dict = {}
    client_type: str = "user"
    is_public_path: bool = check_public_path(request.url.path)

    has_access_token = bool(request.cookies.get("access_token"))
    has_service_id = bool(request.headers.get("X-Service-ID"))

    if has_access_token and has_service_id:
        raise HTTPException(
            status_code=400,
            detail="Ambiguous authentication",
        )
    # Проверяем куки браузера
    if has_access_token:
        user_data = await validate_jwt(request.cookies.get("access_token", None))
        if not (user_data or is_public_path):
            raise HTTPException(status_code=401, detail="Invalid access token")

    # Проверяем хэдеры сервиса
    elif has_service_id:
        user_data, client_type = await parse_service_request(request)
        if not (user_data or is_public_path):
            raise HTTPException(status_code=401, detail="Invalid service request")

    elif not is_public_path:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user_data, client_type


async def request_data_middleware(request: Request):
    """Middleware добавляет в request тип запроса и данные пользователя."""

    user_data, client_type = await parse_request(request)

    request.state.user = user_data
    request.state.client_type = client_type
