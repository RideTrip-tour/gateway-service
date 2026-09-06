import base64
import json
import logging
import time

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

from app.services.cache import (
    CACHE_HEADER,
    build_cache_key,
    filter_cache_headers,
    get_cached_response,
    is_cacheable_request,
    set_cached_response,
)
from config import settings

logger = logging.getLogger("gateway_service.proxy")


async def check_admin_permission(request: Request) -> None:
    return


def is_admin_service(parts: list) -> bool:
    return parts[2] == "admin"


async def get_target_url(request: Request) -> str:
    path = request.url.path
    parts = path.split("/")

    if is_admin_service(parts):
        service = parts[3]
    else:
        service = parts[2]

    request.state.target_service = service

    if service not in settings.service_map:
        logger.info("Service not found service=%s", service)
        raise HTTPException(status_code=404, detail="Service not found")

    target_base_url = settings.service_map[service]
    target_url = f"{target_base_url}{path}"
    return target_url


async def get_headers(request: Request) -> dict:
    blocked_headers = {
        "host",
        # Эти заголовки заполняет только gateway, чтобы клиент не мог их подделать
        "x-user-id",
        "x-user-claims",
        "x-forwarded-for",
        "x-real-ip",
        "x-client-type",
    }
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in blocked_headers
    }

    # Добавляем информацию о пользователе, если он аутентифицирован
    user = getattr(request.state, "user", None)
    if user:
        user_id = user.get("user_id") or user.get("sub") or user.get("id")
        if user_id is not None:
            headers["X-User-ID"] = str(user_id)

        raw_claims = json.dumps(user, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        headers["X-User-Claims"] = base64.urlsafe_b64encode(raw_claims).decode("ascii")

    client_type = getattr(request.state, "client_type", None)
    if client_type:
        headers["X-Client-Type"] = client_type

    client = getattr(request, "client", None)
    client_host = getattr(client, "host", None)
    if client_host:
        headers["X-Forwarded-For"] = client_host
        headers["X-Real-IP"] = client_host

    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        headers["X-Request-ID"] = request_id

    return headers


async def get_responce(request: Request) -> httpx.Response:
    client: httpx.AsyncClient = request.app.state.http_client
    target_url = await get_target_url(request)
    headers = await get_headers(request)

    # Читаем тело входящего запроса как поток
    body_stream = request.stream()

    try:
        started_at = time.perf_counter()
        req = client.build_request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.query_params.multi_items(),
            content=body_stream,
        )
        resp = await client.send(req, stream=True)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Downstream response request_id=%s service=%s status_code=%s duration_ms=%s",
            getattr(request.state, "request_id", None),
            getattr(request.state, "target_service", None),
            resp.status_code,
            duration_ms,
        )
    except httpx.ConnectError:
        logger.warning(
            "Downstream service unavailable request_id=%s service=%s",
            getattr(request.state, "request_id", None),
            getattr(request.state, "target_service", None),
        )
        raise HTTPException(status_code=503, detail="Service is unavailable")
    except httpx.TimeoutException:
        logger.warning(
            "Downstream service timeout request_id=%s service=%s",
            getattr(request.state, "request_id", None),
            getattr(request.state, "target_service", None),
        )
        raise HTTPException(status_code=503, detail="Service is unavailable")

    return resp


async def reverse_proxy(request: Request):
    """
    Проксирует запрос к соответствующему микросервису.
    Корректно прокидывает многозначные Set-Cookie заголовки.
    """
    redis_client = getattr(request.app.state, "redis", None)
    cache_key = None
    if is_cacheable_request(request):
        cache_key = build_cache_key(request)
        cached = await get_cached_response(redis_client, cache_key)
        if cached is not None:
            headers = cached["headers"]
            headers[CACHE_HEADER] = "HIT"
            logger.info(
                "Response cache hit request_id=%s path=%s",
                getattr(request.state, "request_id", None),
                request.url.path,
            )
            return Response(
                content=cached["body"],
                status_code=cached["status_code"],
                headers=headers,
            )

    response = await get_responce(request)
    set_cookie_headers = response.headers.get_list("set-cookie")
    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in {"set-cookie", "content-length"}
    }

    if cache_key is not None:
        body = await response.aread()
        await response.aclose()
        await set_cached_response(
            redis_client,
            cache_key,
            status_code=response.status_code,
            headers=dict(response.headers),
            body=body,
        )
        response_headers = filter_cache_headers(headers)
        response_headers[CACHE_HEADER] = "MISS"
        return Response(
            content=body,
            status_code=response.status_code,
            headers=response_headers,
        )

    # Создаём потоковый ответ
    stream_response = StreamingResponse(
        response.aiter_raw(),
        status_code=response.status_code,
        headers=headers,
        background=BackgroundTask(response.aclose),
    )

    # Set-Cookie нельзя безопасно схлопывать в одну строку:
    # каждый cookie должен быть отдельным заголовком.
    for cookie in set_cookie_headers:
        stream_response.raw_headers.append((b"set-cookie", cookie.encode("utf-8")))
    return stream_response
