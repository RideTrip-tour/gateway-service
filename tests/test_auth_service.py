from unittest.mock import patch

import jwt
import pytest

from app.services.auth import validate_jwt
from config import settings


@pytest.mark.asyncio
async def test_validate_jwt_returns_data_for_valid_token():
    payload = {
        "user_id": 123,
        "is_active": True,
    }

    with patch(
        "app.services.auth.jwt.decode",
        return_value=payload,
    ) as decode_mock:
        result = await validate_jwt("valid-token")

    assert result == payload

    decode_mock.assert_called_once_with(
        "valid-token",
        settings.jwt_secret,
        audience=settings.gateway_name,
        algorithms=settings.jwt_algorithm,
    )


@pytest.mark.asyncio
async def test_validate_jwt_returns_none_for_inactive_user():
    payload = {
        "user_id": 123,
        "is_active": False,
    }

    with patch(
        "app.services.auth.jwt.decode",
        return_value=payload,
    ):
        result = await validate_jwt("valid-token")

    assert result is None


@pytest.mark.asyncio
async def test_validate_jwt_returns_data_when_is_active_missing():
    payload = {
        "user_id": 123,
    }

    with patch(
        "app.services.auth.jwt.decode",
        return_value=payload,
    ):
        result = await validate_jwt("valid-token")

    assert result == payload


@pytest.mark.asyncio
async def test_validate_jwt_returns_none_for_expired_token():
    with patch(
        "app.services.auth.jwt.decode",
        side_effect=jwt.ExpiredSignatureError,
    ):
        result = await validate_jwt("expired-token")

    assert result is None


@pytest.mark.asyncio
async def test_validate_jwt_logs_expired_token():
    with (
        patch(
            "app.services.auth.jwt.decode",
            side_effect=jwt.ExpiredSignatureError,
        ),
        patch(
            "app.services.auth.logger.warning",
        ) as warning_mock,
    ):
        result = await validate_jwt("expired-token")

    assert result is None
    warning_mock.assert_called_once_with("Access token expired")


@pytest.mark.asyncio
async def test_validate_jwt_returns_none_for_invalid_audience():
    with patch(
        "app.services.auth.jwt.decode",
        side_effect=jwt.InvalidAudienceError,
    ):
        result = await validate_jwt("invalid-token")

    assert result is None


@pytest.mark.asyncio
async def test_validate_jwt_returns_none_for_invalid_token():
    with patch(
        "app.services.auth.jwt.decode",
        side_effect=jwt.InvalidTokenError("Invalid token"),
    ):
        result = await validate_jwt("invalid-token")

    assert result is None


@pytest.mark.asyncio
async def test_validate_jwt_returns_none_for_empty_payload():
    with patch(
        "app.services.auth.jwt.decode",
        return_value={},
    ):
        result = await validate_jwt("valid-token")

    assert result is None
