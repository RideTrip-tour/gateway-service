import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret: str = os.getenv("JWT_SECRET", "secret")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    gateway_name: str = os.getenv("GATEWAY_NAME", "Gate")

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_ttl: int = 300  # время жизни кеша по умолчанию
    rate_limit: int = 100  # запросов в минуту
    public_paths: list[str] = [
        "/health",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/docs",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/verify",
    ]
    service_map: dict[str, str] = {
        "auth": "http://auth-service:8000",
        "plans": "http://plans-service:8000",
        "locations": "http://locations-service:8000",
        "users": "http://users-service:8000",
        "activities": "http://activities-service:8000",
        "routes": "http://routes-service:8000",
        "departure": "http://departure-service:8000",
        "pricing": "http://pricing-service:8000",
        "pdf": "http://pdf-service:8000",
        "bot": "http://bot-service:8000",
    }


settings = Settings()
