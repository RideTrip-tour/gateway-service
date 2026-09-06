import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from app.middleware.auth import request_data_middleware
from app.middleware.request_logging import request_logging_middleware
from app.services.proxy import reverse_proxy
from app.utils.logging import LOGGING_CONFIG
from config import settings

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("gateway_service")

BASE_DIR = Path(__file__).resolve().parent
DOCS_FILE = BASE_DIR / "app" / "services" / "docs.html"
DOCS_CONTENT = DOCS_FILE.read_text(encoding="utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Перед стартом приложения
    logger.info("gateway-service is starting up")
    redis_client = await redis.Redis.from_url(settings.redis_url)
    app.state.redis = redis_client
    await FastAPILimiter.init(redis_client)
    # Создаем один httpx клиент на все время жизни приложения
    app.state.http_client = httpx.AsyncClient(timeout=settings.proxy_timeout)
    yield
    # Перед остановкой приложения
    await app.state.http_client.aclose()
    await redis_client.aclose()
    logger.info("gateway-service is shutting down")


app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# Подключаем middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    try:
        await request_data_middleware(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    return await request_logging_middleware(request, call_next)


# Health check
@app.get(
    "/health", dependencies=[Depends(RateLimiter(times=settings.rate_limit, minutes=1))]
)
async def health_check():
    return {"status": "ok"}


# Обработчик для favicon.ico, чтобы избежать ошибок 404 в логах
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Маршрут для проксирования. Должен быть последним.
@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_requests(request: Request):
    return await reverse_proxy(request)


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    return HTMLResponse(
        content=DOCS_CONTENT,
        status_code=200,
    )
