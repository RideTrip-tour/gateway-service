from fastapi import HTTPException, Request

from app.utils.cryptography import verify_request_signature
from config import settings


async def validate_admin_permission(request: Request) -> None:
    """
    Права администратора, выкидывает исключение, если не удалось проверить.
    """
    service_id = request.headers.get("X-Service-ID")
    user_context = request.headers.get("X-User-Context")
    service_token = request.headers.get("X-Service-Token")
    timestamp = request.headers.get("X-Timestamp")
    nonce = request.headers.get("X-Nonce")
    signature = request.headers.get("X-Signature")

    if not all(
        [
            service_id,
            user_context,
            service_token,
            timestamp,
            nonce,
            signature,
        ]
    ):
        raise HTTPException(status_code=401, detail="Invalid admin authentication")

    public_key_data = settings.service_public_keys.get(service_id)
    if not public_key_data:
        raise HTTPException(
            status_code=401,
            detail="Unknown service",
        )

    # Проверяем подпись запроса
    await verify_request_signature(
        request=request,
        public_key_data=public_key_data,
        signature=signature,
    )
