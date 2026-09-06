import base64
import hashlib
import json
import logging
from typing import Any
from urllib.parse import urlencode

from fastapi import Request
from redis.asyncio import Redis

from config import settings

logger = logging.getLogger("gateway_service.cache")

CACHE_HEADER = "X-Gateway-Cache"


def path_matches(path: str, allowed_path: str) -> bool:
    normalized = allowed_path.rstrip("/")
    return path == normalized or path.startswith(f"{normalized}/")


def is_cacheable_request(request: Request) -> bool:
    if not settings.cache_enabled:
        return False
    if request.method not in {"GET", "HEAD"}:
        return False
    if not settings.cacheable_paths:
        return False
    if request.cookies:
        return False
    if request.headers.get("authorization"):
        return False
    if request.headers.get("x-service-id") or request.headers.get("x-service-token"):
        return False
    if request.headers.get("x-user-id") or request.headers.get("x-user-claims"):
        return False
    if getattr(request.state, "user", None):
        return False

    return any(
        path_matches(request.url.path, path) for path in settings.cacheable_paths
    )


def is_cacheable_response(status_code: int, headers: dict[str, str]) -> bool:
    if status_code != 200:
        return False
    if any(key.lower() == "set-cookie" for key in headers):
        return False

    cache_control = headers.get("cache-control", "").lower()
    return "no-store" not in cache_control and "private" not in cache_control


def build_cache_key(request: Request) -> str:
    accept = request.headers.get("accept", "")
    accept_language = request.headers.get("accept-language", "")
    query = urlencode(sorted(request.query_params.multi_items()), doseq=True)
    raw_key = (
        f"{request.method}\n{request.url.path}\n{query}\n{accept}\n{accept_language}"
    )
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"gateway:response-cache:{digest}"


def filter_cache_headers(headers: dict[str, str]) -> dict[str, str]:
    blocked_headers = {
        "connection",
        "content-length",
        "set-cookie",
        "transfer-encoding",
    }
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in blocked_headers
    }


async def get_cached_response(
    redis_client: Redis | None,
    cache_key: str,
) -> dict[str, Any] | None:
    if redis_client is None:
        return None

    cached = await redis_client.get(cache_key)
    if cached is None:
        return None

    if isinstance(cached, bytes):
        cached = cached.decode("utf-8")

    try:
        payload = json.loads(cached)
    except json.JSONDecodeError:
        logger.warning("Invalid cached response payload for key %s", cache_key)
        return None

    payload["body"] = base64.b64decode(payload["body"])
    return payload


async def set_cached_response(
    redis_client: Redis | None,
    cache_key: str,
    *,
    status_code: int,
    headers: dict[str, str],
    body: bytes,
) -> None:
    if redis_client is None:
        return
    if not is_cacheable_response(status_code, headers):
        return

    payload = {
        "status_code": status_code,
        "headers": filter_cache_headers(headers),
        "body": base64.b64encode(body).decode("ascii"),
    }
    await redis_client.set(
        cache_key,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        ex=settings.response_cache_ttl,
    )
