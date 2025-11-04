from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException, Request
from app.services.proxy import get_headers, get_responce, get_target_url
from fastapi.testclient import TestClient
import json


service = "users"
service_url = "http://users:8000"
mock_service_map = {service: service_url}


class MockAsyncIterator:
    """A helper class to create a mock asynchronous iterator."""

    def __init__(self, data: bytes = b""):
        self._data = data

    async def __aiter__(self):
        yield self._data


@pytest.mark.asyncio
async def test_get_target_url_not_found():
    """Тест исключения при обращении к несуществующему сервису."""
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/not_found_sevice/get_item/1"

    # Используем patch для временной подмены service_map
    with patch("app.services.proxy.settings.service_map", mock_service_map):
        with pytest.raises(HTTPException) as e:
            await get_target_url(mock_request)
        assert e.value.status_code == 404
        assert e.value.detail == "Service not found"


@pytest.mark.asyncio
async def test_get_target_url_found():
    """Тест успешного обращения к сервису."""
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = f"/{service}/get_item/1"
    with patch("app.services.proxy.settings.service_map", mock_service_map):
        target_url = await get_target_url(mock_request)
        assert target_url == f"{service_url}/get_item/1"


@pytest.mark.asyncio
async def test_get_headers_unauthenticated():
    """Тест: для анонимного пользователя заголовок X-User-ID не добавляется."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"host": "test.com", "accept": "application/json"}
    mock_request.state.user = None

    headers = await get_headers(mock_request)

    assert "X-User-ID" not in headers
    assert "host" not in headers
    assert headers["accept"] == "application/json"


@pytest.mark.asyncio
async def test_get_headers_authenticated():
    """Тест: для аутентифицированного пользователя добавляется заголовок X-User-ID."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.state.user = {"user_id": 123}

    headers = await get_headers(mock_request)

    assert headers["X-User-ID"] == "123"


@pytest.mark.asyncio
async def test_get_response_success(httpx_mock):
    """Тест успешного получения ответа от микросервиса."""
    # 1. Настраиваем мок httpx
    httpx_mock.add_response(status_code=200, json={"data": "ok"})

    # 2. Создаем моковый Request
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.http_client = httpx.AsyncClient()
    mock_request.url.path = f"/{service}/test"
    mock_request.method = "GET"
    mock_request.headers = {}
    mock_request.query_params = {}
    # Use a proper mock for the async stream. For a GET request, the body is empty.
    mock_request.stream.return_value = MockAsyncIterator()
    mock_request.state.user = None

    # 3. Вызываем функцию и проверяем результат
    with patch("app.services.proxy.settings.service_map", mock_service_map):
        response = await get_responce(mock_request)

    # Перед доступом к .json() у стримингового ответа, его нужно прочитать
    await response.aread()
    assert response.status_code == 200
    assert response.json() == {"data": "ok"}


@pytest.mark.asyncio
async def test_get_response_service_unavailable(httpx_mock):
    """Тест: если сервис недоступен, get_responce вызывает HTTPException 503."""
    httpx_mock.add_exception(httpx.ConnectError("Connection failed"))
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.http_client = httpx.AsyncClient()
    mock_request.url.path = f"/{service}/test"
    mock_request.method = "GET"
    mock_request.headers = {}
    mock_request.query_params = {}
    # Use a proper mock for the async stream.
    mock_request.stream.return_value = MockAsyncIterator()
    mock_request.state.user = None

    with patch("app.services.proxy.settings.service_map", mock_service_map):
        with pytest.raises(HTTPException) as e:
            await get_responce(mock_request)
        assert e.value.status_code == 503
        assert e.value.detail == "Service is unavailable"


@pytest.mark.asyncio
async def test_reverse_proxy_integration(client: TestClient, httpx_mock):
    """
    Интеграционный тест для reverse_proxy.
    Проверяет проксирование POST-запроса с телом и заголовками.
    """
    # 1. Готовим данные для запроса и мока
    request_body = {"name": "test_user"}
    response_body = {"id": 1, "name": "test_user"}
    target_url = f"{service_url}/"

    # 2. Настраиваем httpx_mock для имитации ответа от users-service
    httpx_mock.add_response(
        method="POST",
        url=target_url,
        json=response_body,
        status_code=201,
        match_content=json.dumps(request_body).encode("utf-8"),
    )
    with patch(
        "app.middleware.auth.validate_jwt", return_value={"id": 1, "name": "test_user"}
    ), patch("app.services.proxy.settings.service_map", mock_service_map):
        # 3. Отправляем запрос на gateway с помощью TestClient
        response = client.post(
            f"/{service}/",
            json=request_body,
            headers={
                "X-Custom-Header": "value",
                "Authorization": "Bearer test_token",
            },
        )

    # 4. Проверяем ответ, полученный от gateway
    assert response.status_code == 201
    assert response.json() == response_body

    # 5. (Опционально) Проверяем, что запрос к микросервису был сделан с правильными заголовками
    proxied_request = httpx_mock.get_request()
    assert proxied_request.headers["x-custom-header"] == "value"
