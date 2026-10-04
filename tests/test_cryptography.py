import base64
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import HTTPException, Request

from app.utils.cryptography import (
    build_signing_message,
    verify_request_signature,
)


def make_signature(
    private_key,
    *,
    service_id: str,
    method: str,
    path: str,
    query: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    user_context: str = "",
) -> str:
    body_hash = hashlib.sha256(body).hexdigest()

    message = build_signing_message(
        service_id=service_id,
        method=method,
        path=path,
        query=query,
        timestamp=timestamp,
        nonce=nonce,
        body_hash=body_hash,
        user_context=user_context,
    )

    signature = private_key.sign(
        message.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    return base64.b64encode(signature).decode()


@pytest.mark.asyncio
async def test_verify_request_signature_success(rsa_keys):
    private_key, public_key_pem = rsa_keys

    timestamp = str(int(time.time()))
    body = b'{"test": true}'

    request = MagicMock(spec=Request)
    request.body = AsyncMock(return_value=body)
    request.method = "POST"

    request.url.path = "/api/test"
    request.url.query = "foo=bar"

    request.headers = {
        "X-Service-ID": "auth-service",
        "X-Nonce": "nonce-123",
        "X-Timestamp": timestamp,
        "X-User-Context": "user-123",
    }

    request.app.state.redis.set = AsyncMock(return_value=True)

    signature = make_signature(
        private_key,
        service_id="auth-service",
        method="POST",
        path="/api/test",
        query="foo=bar",
        timestamp=timestamp,
        nonce="nonce-123",
        body=body,
        user_context="user-123",
    )

    result = await verify_request_signature(
        request,
        public_key_pem,
        signature,
    )

    assert result is None

    request.app.state.redis.set.assert_awaited_once_with(
        "service-request-nonce:auth-service:nonce-123",
        "1",
        ex=60,
        nx=True,
    )


@pytest.mark.asyncio
async def test_verify_request_signature_invalid_signature(rsa_keys):
    _, public_key_pem = rsa_keys

    request = MagicMock(spec=Request)
    request.body = AsyncMock(return_value=b"body")
    request.method = "POST"

    request.url.path = "/api/test"
    request.url.query = ""

    request.headers = {
        "X-Service-ID": "auth-service",
        "X-Nonce": "nonce-123",
        "X-Timestamp": str(int(time.time())),
    }

    invalid_signature = base64.b64encode(b"invalid-signature").decode()

    with pytest.raises(HTTPException) as exc:
        await verify_request_signature(
            request,
            public_key_pem,
            invalid_signature,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid service signature"
