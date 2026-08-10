from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, Request
import httpx
import pytest
from starlette.datastructures import QueryParams


from app.services.proxy import get_headers, get_responce, get_target_url, reverse_proxy

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
    path = f"/api/{service}/get_item/1"
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = path
    with patch("app.services.proxy.settings.service_map", mock_service_map):
        target_url = await get_target_url(mock_request)
        assert target_url == f"{service_url}{path}"


@pytest.mark.asyncio
async def test_get_headers_unauthenticated():
    """Тест: для анонимного пользователя заголовок X-User-ID не добавляется."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"host": "test.com", "accept": "application/json"}
    mock_request.state = SimpleNamespace(user=None)
    mock_request.client = SimpleNamespace(host="10.0.0.5")

    headers = await get_headers(mock_request)

    assert "X-User-ID" not in headers
    assert "host" not in headers
    assert headers["accept"] == "application/json"
    assert headers["X-Forwarded-For"] == "10.0.0.5"
    assert headers["X-Real-IP"] == "10.0.0.5"


@pytest.mark.asyncio
async def test_get_headers_authenticated():
    """Тест: для аутентифицированного пользователя добавляется заголовок X-User-ID."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.state = SimpleNamespace(user={"user_id": 123})
    mock_request.client = SimpleNamespace(host="10.0.0.6")

    headers = await get_headers(mock_request)

    assert headers["X-User-ID"] == "123"
    assert headers["X-Forwarded-For"] == "10.0.0.6"
    assert headers["X-Real-IP"] == "10.0.0.6"


@pytest.mark.asyncio
async def test_get_headers_authenticated_uses_sub_fallback():
    """Если user_id отсутствует, заголовок должен браться из sub."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.state = SimpleNamespace(user={"sub": "456"})
    mock_request.client = SimpleNamespace(host="10.0.0.7")

    headers = await get_headers(mock_request)

    assert headers["X-User-ID"] == "456"
    assert headers["X-Forwarded-For"] == "10.0.0.7"
    assert headers["X-Real-IP"] == "10.0.0.7"


@pytest.mark.asyncio
async def test_get_headers_overwrites_forwarded_headers():
    """Клиентские X-Forwarded-For/X-Real-IP не должны проходить в downstream."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {
        "x-forwarded-for": "1.2.3.4",
        "x-real-ip": "1.2.3.4",
        "accept": "application/json",
    }
    mock_request.state = SimpleNamespace(user=None)
    mock_request.client = SimpleNamespace(host="10.0.0.8")

    headers = await get_headers(mock_request)

    assert headers["accept"] == "application/json"
    assert headers["X-Forwarded-For"] == "10.0.0.8"
    assert headers["X-Real-IP"] == "10.0.0.8"


@pytest.mark.asyncio
async def test_get_response_success(httpx_mock):
    """Тест успешного получения ответа от микросервиса."""
    # 1. Настраиваем мок httpx
    httpx_mock.add_response(status_code=200, json={"data": "ok"})

    # 2. Создаем моковый Request
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.http_client = httpx.AsyncClient()
    mock_request.url.path = f"/api/{service}/test"
    mock_request.method = "GET"
    mock_request.headers = {}
    mock_request.query_params = QueryParams()
    mock_request.client = SimpleNamespace(host="10.0.0.9")
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
    mock_request.url.path = f"/api/{service}/test"
    mock_request.method = "GET"
    mock_request.headers = {}
    mock_request.query_params = QueryParams()
    mock_request.client = SimpleNamespace(host="10.0.0.9")
    # Use a proper mock for the async stream.
    mock_request.stream.return_value = MockAsyncIterator()
    mock_request.state.user = None

    with patch("app.services.proxy.settings.service_map", mock_service_map):
        with pytest.raises(HTTPException) as e:
            await get_responce(mock_request)
        assert e.value.status_code == 503
        assert e.value.detail == "Service is unavailable"


@pytest.mark.asyncio
async def test_reverse_proxy_integration(httpx_mock):
    """
    Интеграционный тест для reverse_proxy.
    Проверяет проксирование POST-запроса с телом и заголовками.
    """
    # 1. Готовим данные для запроса и мока
    request_body = {"name": "test_user"}
    user_data = {"id": 1, "name": "test_user", "is_active": True}
    # Путь, по которому gateway обращается к целевому сервису
    path = f"/api/{service}/"
    target_url = f"{service_url}{path}"

    # Настраиваем httpx_mock для имитации ответа от users-service
    httpx_mock.add_response(
        method="POST",
        url=target_url,
        json=user_data,
        status_code=201,
        match_json=request_body,
    )
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.http_client = httpx.AsyncClient()
    mock_request.url.path = path
    mock_request.method = "POST"
    mock_request.headers = {"content-type": "application/json"}
    mock_request.query_params = QueryParams()
    mock_request.client = SimpleNamespace(host="10.0.0.10")
    mock_request.stream.return_value = MockAsyncIterator(b'{"name":"test_user"}')
    mock_request.state.user = user_data

    with patch("app.services.proxy.settings.service_map", mock_service_map):
        response = await reverse_proxy(mock_request)

    # Проверяем ответ, полученный от gateway
    body = b"".join([chunk async for chunk in response.body_iterator])

    assert response.status_code == 201, f"Ответ: {body!r}"
    assert body == b'{"id":1,"name":"test_user","is_active":true}'


@pytest.mark.asyncio
async def test_get_response_preserves_multiple_query_params():
    from app.services.proxy import get_responce

    received_request = None

    async def handler(request: httpx.Request):
        nonlocal received_request
        received_request = request

        return httpx.Response(200, request=request)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        mock_request = MagicMock(spec=Request)

        mock_request.app.state.http_client = client
        mock_request.method = "GET"
        mock_request.query_params = QueryParams(
            [
                ("region", "Московская область"),
                ("region", "Кемеровская область"),
                ("limit", "100"),
            ]
        )
        mock_request.stream.return_value = MockAsyncIterator()

        with (
            patch(
                "app.services.proxy.get_target_url",
                new=AsyncMock(return_value="http://locations-service/api/locations"),
            ),
            patch(
                "app.services.proxy.get_headers",
                new=AsyncMock(return_value={}),
            ),
        ):
            await get_responce(mock_request)

    assert received_request.url.params.get_list("region") == [
        "Московская область",
        "Кемеровская область",
    ]
