import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from starlette.responses import JSONResponse

from app.middleware.request_logging import request_logging_middleware


@pytest.mark.asyncio
async def test_request_logging_middleware_uses_existing_request_id(caplog):
    expected_request_id = "test-request-id"
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/test"
    request.state = MagicMock()
    request.state.user = {
        "user_id": "123",
    }
    request.state.target_service = "users-service"
    request.state.client_type = "web"
    request.state.request_id = expected_request_id

    client = MagicMock()
    client.host = "127.0.0.1"
    request.client = client

    response = JSONResponse({"status": "ok"}, status_code=200)

    call_next = AsyncMock(return_value=response)

    with caplog.at_level(logging.INFO, logger="gateway_service"):
        from app.middleware.request_logging import logger

        logger.propagate = True
        result = await request_logging_middleware(
            request,
            call_next,
        )
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "INFO"
    assert f"request_id={expected_request_id}" in record.getMessage()
    assert result is response

    call_next.assert_awaited_once_with(request)
