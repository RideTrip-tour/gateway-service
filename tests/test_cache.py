from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import fakeredis.aioredis
import httpx
import pytest
from fastapi import Request
from starlette.datastructures import QueryParams

from app.middleware.auth import request_data_middleware
from app.services.cache import CACHE_HEADER, is_cacheable_request
from app.services.proxy import reverse_proxy


class MockAsyncIterator:
    def __init__(self, data: bytes = b""):
        self._data = data

    async def __aiter__(self):
        yield self._data


def build_request(
    *,
    redis_client,
    http_client: httpx.AsyncClient,
    cookies: dict | None = None,
):
    request = MagicMock(spec=Request)
    request.app.state.redis = redis_client
    request.app.state.http_client = http_client
    request.url.path = "/api/locations"
    request.url.query = "limit=20"
    request.method = "GET"
    request.headers = {"accept": "application/json"}
    request.cookies = cookies or {}
    request.query_params = QueryParams([("limit", "20")])
    request.client = SimpleNamespace(host="10.0.0.11")
    request.stream.return_value = MockAsyncIterator()
    request.state.user = None
    request.state.client_type = None
    request.state.request_id = "request-id"
    return request


def test_is_cacheable_request_rejects_cookie():
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/api/locations"
    request.cookies = {"access_token": "token"}
    request.headers = {}

    with patch("app.services.cache.settings.cacheable_paths", ["/api/locations"]):
        assert is_cacheable_request(request) is False


def test_is_cacheable_request_rejects_similar_path():
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/api/locations-extra"
    request.cookies = {}
    request.headers = {}
    request.state.user = None

    with patch("app.services.cache.settings.cacheable_paths", ["/api/locations"]):
        assert is_cacheable_request(request) is False


@pytest.mark.asyncio
async def test_request_data_middleware_allows_anonymous_cacheable_path():
    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/locations"),
        cookies={},
        state=SimpleNamespace(),
        headers={},
    )

    with (
        patch("app.middleware.auth.settings.public_paths", []),
        patch("app.utils.auth_user.settings.cacheable_paths", ["/api/locations"]),
    ):
        await request_data_middleware(request)

    assert request.state.user == {}
    assert request.state.client_type == "user"


@pytest.mark.asyncio
async def test_reverse_proxy_caches_public_get(httpx_mock):
    redis_client = fakeredis.aioredis.FakeRedis()
    target_url = "http://location-service:8000/api/locations"
    httpx_mock.add_response(
        method="GET",
        url=f"{target_url}?limit=20",
        json={"items": []},
        status_code=200,
    )

    async with httpx.AsyncClient() as http_client:
        with (
            patch(
                "app.services.proxy.settings.service_map",
                {"locations": "http://location-service:8000"},
            ),
            patch("app.services.cache.settings.cacheable_paths", ["/api/locations"]),
        ):
            first_response = await reverse_proxy(
                build_request(redis_client=redis_client, http_client=http_client)
            )
            second_response = await reverse_proxy(
                build_request(redis_client=redis_client, http_client=http_client)
            )

    assert first_response.status_code == 200
    assert first_response.headers[CACHE_HEADER] == "MISS"
    assert first_response.body == b'{"items":[]}'
    assert second_response.status_code == 200
    assert second_response.headers[CACHE_HEADER] == "HIT"
    assert second_response.body == b'{"items":[]}'


@pytest.mark.asyncio
async def test_reverse_proxy_does_not_cache_request_with_cookie(httpx_mock):
    redis_client = fakeredis.aioredis.FakeRedis()
    target_url = "http://location-service:8000/api/locations"
    httpx_mock.add_response(
        method="GET",
        url=f"{target_url}?limit=20",
        json={"items": [1]},
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{target_url}?limit=20",
        json={"items": [2]},
        status_code=200,
    )

    async with httpx.AsyncClient() as http_client:
        with (
            patch(
                "app.services.proxy.settings.service_map",
                {"locations": "http://location-service:8000"},
            ),
            patch("app.services.cache.settings.cacheable_paths", ["/api/locations"]),
        ):
            first_response = await reverse_proxy(
                build_request(
                    redis_client=redis_client,
                    http_client=http_client,
                    cookies={"access_token": "token"},
                )
            )
            second_response = await reverse_proxy(
                build_request(
                    redis_client=redis_client,
                    http_client=http_client,
                    cookies={"access_token": "token"},
                )
            )

    first_body = b"".join([chunk async for chunk in first_response.body_iterator])
    second_body = b"".join([chunk async for chunk in second_response.body_iterator])

    assert first_body == b'{"items":[1]}'
    assert second_body == b'{"items":[2]}'
