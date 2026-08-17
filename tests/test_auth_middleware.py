import secrets
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.middleware.auth import request_data_middleware


@pytest.mark.asyncio
async def test_request_data_middleware_user_data_in_request_state_for_user_request():
    """Middleware должно сохранять decoded JWT в request.state.user."""
    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/users/me"),
        cookies={"access_token": "token"},
        state=SimpleNamespace(),
        headers={},
    )

    with (
        patch("app.middleware.auth.settings.public_paths", []),
        patch(
            "app.middleware.auth.validate_jwt",
            new_callable=AsyncMock,
        ) as mock_validate_jwt,
    ):
        mock_validate_jwt.return_value = {"sub": "123", "is_active": True}
        await request_data_middleware(request)

    assert request.state.user == {"sub": "123", "is_active": True}
    assert request.state.client_type == "user"


@pytest.mark.asyncio
async def test_request_data_middleware_user_data_in_request_state_for_service_request():
    """Middleware должен добавлять название сервиса и данные пользователя в state, если запрос пришел от сервиса"""
    service_name = "service"
    token = "Token"
    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/users/me"),
        cookies={},
        state=SimpleNamespace(),
        headers={
            "X-Service-ID": service_name,
            "X-User-Context": "jwt",
            "X-Service-Token": token,
        },
    )

    with (
        patch("app.middleware.auth.settings.public_paths", []),
        patch("app.middleware.auth.settings.service_tokens", {service_name: token}),
        patch(
            "app.middleware.auth.validate_jwt",
            new_callable=AsyncMock,
        ) as mock_validate_jwt,
    ):
        mock_validate_jwt.return_value = {"sub": "123", "is_active": True}
        await request_data_middleware(request)

    assert request.state.user == {"sub": "123", "is_active": True}
    assert request.state.client_type == service_name


@pytest.mark.asyncio
async def test_request_data_middleware_user_data_in_request_state_for_admin_request():
    """
    При прохождении проверок нужно что бы в client_type был admin
    """
    service_name = "admin"
    user_context = "jwt"
    token = "Token"
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(32)

    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/users/me"),
        cookies={},
        state=SimpleNamespace(),
        headers={
            "X-Service-ID": service_name,
            "X-User-Context": user_context,
            "X-Service-Token": token,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": "signature",
        },
        body=AsyncMock(side_effect=lambda: b'{"body": "kdld"}'),
        method="POST",
    )

    with (
        patch("app.middleware.auth.settings.public_paths", []),
        patch("app.middleware.auth.settings.service_tokens", {service_name: token}),
        patch(
            "app.middleware.auth.settings.service_public_keys",
            {
                service_name: "public-key",
            },
        ),
        patch(
            "app.middleware.auth.validate_jwt",
            new_callable=AsyncMock,
        ) as mock_validate_jwt,
        patch(
            "app.utils.auth_service.verify_request_signature",
        ),
    ):
        mock_validate_jwt.return_value = {"sub": "123", "is_active": True}
        await request_data_middleware(request)

    assert request.state.user == {"sub": "123", "is_active": True}
    assert request.state.client_type == service_name
