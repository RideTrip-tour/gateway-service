import base64
import hashlib
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException, Request


def build_signing_message(
    service_id: str,
    method: str,
    path: str,
    query: str,
    timestamp: str,
    nonce: str,
    body_hash: str,
    user_context: str,
):
    parts = [
        service_id,
        method,
        path,
        query,
        timestamp,
        nonce,
        body_hash,
        user_context,
    ]

    return "\n".join(parts)


async def verify_request_signature(
    request: Request, public_key_data: str, signature: str
) -> None:
    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest()
    service_id = request.headers.get("X-Service-ID")
    nonce = request.headers.get("X-Nonce")
    timestamp = request.headers.get("X-Timestamp")

    message = build_signing_message(
        service_id=service_id,
        method=request.method,
        path=request.url.path,
        query=request.url.query,
        timestamp=timestamp,
        nonce=nonce,
        body_hash=body_hash,
        user_context=request.headers.get("X-User-Context"),
    )

    signature_bytes = base64.b64decode(signature)
    public_key = serialization.load_pem_public_key(public_key_data.encode())
    try:
        # Проверяем подпись
        public_key.verify(
            signature_bytes,
            message.encode(),
        )
    except InvalidSignature as ex:
        raise HTTPException(
            status_code=401,
            detail="Invalid service signature",
        ) from ex

    # Проверяем timestamp, запрос не позднее 30 секунд
    if abs(time.time() - int(timestamp)) > 30:
        raise HTTPException(
            status_code=401,
            detail="Request expired",
        )

    # Проdеряем nonce, что этот запрос ещё не исполнялся
    key = f"service-request-nonce:{service_id}:{nonce}"
    created = await request.app.state.redis.set(
        key,
        "1",
        ex=60,
        nx=True,
    )

    if not created:
        raise HTTPException(
            status_code=401,
            detail="Request replay detected",
        )
