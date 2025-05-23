from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import Depends, FastAPI, Request
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from app.middleware.auth import jwt_middleware
from config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Перед стартом приложения
    client = await redis.Redis.from_url(settings.redis_url)
    await FastAPILimiter.init(client)
    yield
    # Перед остановкой приложения
    pass


app = FastAPI(lifespan=lifespan)

# Подключаем middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    await jwt_middleware(request)
    return await call_next(request)


# Health check
@app.get("/health", dependencies=[Depends(RateLimiter(times=settings.rate_limit, minutes=1))])
async def health_check():
    return {"status": "ok"}
