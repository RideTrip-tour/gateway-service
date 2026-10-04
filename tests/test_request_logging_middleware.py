from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from starlette.responses import JSONResponse

from app.middleware.request_logging import request_logging_middleware


@pytest.mark.asyncio
async def test_request_logging_middleware_uses_existing_request_id():
    request = MagicMock(spec=Request)
    request.headers = {"X-Request-ID": "existing-request-id"}
    request.method = "GET"
    request.url.path = "/test"
    request.state = MagicMock()
    request.state.user = {
        "user_id": "123",
    }
    request.state.target_service = "users-service"
    request.state.client_type = "web"

    client = MagicMock()
    client.host = "127.0.0.1"
    request.client = client

    response = JSONResponse({"status": "ok"}, status_code=200)

    call_next = AsyncMock(return_value=response)

    result = await request_logging_middleware(
        request,
        call_next,
    )

    assert result is response
    assert request.state.request_id == "existing-request-id"
    assert result.headers["X-Request-ID"] == "existing-request-id"

    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_request_logging_middleware_generates_request_id():
    request = MagicMock(spec=Request)
    request.headers = {}
    request.method = "GET"
    request.url.path = "/test"
    request.state = MagicMock()

    request.state.user = None
    request.state.target_service = None
    request.state.client_type = None
    request.client = None

    response = JSONResponse({"status": "ok"}, status_code=200)

    call_next = AsyncMock(return_value=response)

    with patch(
        "app.middleware.request_logging.uuid.uuid4",
        return_value="generated-request-id",
    ):
        result = await request_logging_middleware(
            request,
            call_next,
        )

    assert request.state.request_id == "generated-request-id"
    assert result.headers["X-Request-ID"] == "generated-request-id"
