import base64
import json
import logging

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from config import settings

logger = logging.getLogger(__name__)


async def check_admin_permission():
    return


def is_admin_service(parts: list) -> bool:
    return parts[2] == "admin"


async def get_target_url(request: Request) -> str:
    path = request.url.path
    parts = path.split("/")

    if is_admin_service(parts):
        await check_admin_permission()
        service = parts[3]
    else:
        service = parts[2]

    if service not in settings.service_map:
        logger.info(f"Сервис не найден {service}")
        raise HTTPException(status_code=404, detail="Service not found")

    target_base_url = settings.service_map[service]
    target_url = f"{target_base_url}{path}"
    logger.info("Target_url: %s", target_url)
    return target_url


async def get_headers(request: Request) -> dict:
    blocked_headers = {
        "host",
        # Эти заголовки заполняет только gateway, чтобы клиент не мог их подделать
        "x-user-id",
        "x-user-claims",
        "x-forwarded-for",
        "x-real-ip",
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

    client = getattr(request, "client", None)
    client_host = getattr(client, "host", None)
    if client_host:
        headers["X-Forwarded-For"] = client_host
        headers["X-Real-IP"] = client_host

    return headers


async def get_responce(request: Request) -> httpx.Response:
    client: httpx.AsyncClient = request.app.state.http_client
    target_url = await get_target_url(request)
    headers = await get_headers(request)

    # Читаем тело входящего запроса как поток
    body_stream = request.stream()

    try:
        req = client.build_request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.query_params.multi_items(),
            content=body_stream,
        )
        resp = await client.send(req, stream=True)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Service is unavailable")

    return resp


async def reverse_proxy(request: Request):
    """
    Проксирует запрос к соответствующему микросервису.
    Корректно прокидывает многозначные Set-Cookie заголовки.
    """
    response = await get_responce(request)
    set_cookie_headers = response.headers.get_list("set-cookie")
    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in {"set-cookie", "content-length"}
    }

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
