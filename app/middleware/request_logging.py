import logging
import time
import uuid

from fastapi import Request

logger = logging.getLogger("gateway_service")


async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:
        logger.exception(
            "Unhandled request error request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        raise
    finally:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        user = getattr(request.state, "user", None) or {}
        user_id = user.get("user_id") or user.get("sub") or user.get("id")
        client = getattr(request, "client", None)
        client_host = getattr(client, "host", None)
        target_service = getattr(request.state, "target_service", None)
        client_type = getattr(request.state, "client_type", None)

        logger.info(
            "request_id=%s method=%s path=%s status_code=%s duration_ms=%s "
            "client_ip=%s client_type=%s user_id=%s target_service=%s",
            request_id,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            client_host,
            client_type,
            user_id,
            target_service,
        )
        if "response" in locals():
            response.headers["X-Request-ID"] = request_id
