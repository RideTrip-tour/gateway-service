from contextlib import asynccontextmanager

import redis.asyncio as redis
import httpx
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from app.middleware.auth import jwt_middleware
from app.services.proxy import reverse_proxy
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Перед стартом приложения
    redis_client = await redis.Redis.from_url(settings.redis_url)
    await FastAPILimiter.init(redis_client)
    # Создаем один httpx клиент на все время жизни приложения
    app.state.http_client = httpx.AsyncClient()
    yield
    # Перед остановкой приложения
    await app.state.http_client.aclose()
    await FastAPILimiter.close()


app = FastAPI(lifespan=lifespan)


# Подключаем middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    await jwt_middleware(request)
    return await call_next(request)


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
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
)
async def proxy_requests(request: Request):
    return await reverse_proxy(request)
