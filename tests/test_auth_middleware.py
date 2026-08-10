from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.middleware.auth import jwt_middleware


@pytest.mark.asyncio
async def test_jwt_middleware_stores_user_in_request_state():
    """Middleware должно сохранять decoded JWT в request.state.user."""
    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/users/me"),
        cookies={"access_token": "token"},
        state=SimpleNamespace(),
    )

    with (
        patch("app.middleware.auth.settings.public_paths", []),
        patch(
            "app.middleware.auth.validate_jwt",
            new_callable=AsyncMock,
        ) as mock_validate_jwt,
    ):
        mock_validate_jwt.return_value = {"sub": "123", "is_active": True}
        await jwt_middleware(request)

    assert request.state.user == {"sub": "123", "is_active": True}
