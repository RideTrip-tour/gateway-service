import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret: str = "secret"
    jwt_algorithm: str = "HS256"
    gateway_name: str = "Gate"
    debug: bool = False

    # Redis
    redis_url: str = "redis://redis:6379"
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
        "users": "http://auth-service:8000",
        "activities": "http://activities-service:8000",
        "routes": "http://routes-service:8000",
        "departure": "http://departure-service:8000",
        "pricing": "http://pricing-service:8000",
        "pdf": "http://pdf-service:8000",
        "bot": "http://bot-service:8000",
    }
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
