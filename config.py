from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://127.0.0.1:6379"
    redis_ttl: int = 300  # время жизни кеша по умолчанию
    rate_limit: int = 100  # запросов в минуту
    public_paths: list[str] = [
        "/health",
        "/auth/login",
        "/auth/register",
        "/docs",
        "/openapi.json",
        "/redoc",
    ]
    service_map: dict[str, str] = {
        "auth": "http://127.0.0.1:8001/api",
        "plans": "http://plans-service:8001",
        "locations": "http://locations-service:8002",
        "users": "http://users-service:8003",
        "activities": "http://activities-service:8004",
        "routes": "http://routes-service:8005",
        "departure": "http://departure-service:8006",
        "pricing": "http://pricing-service:8007",
        "pdf": "http://pdf-service:8008",
        "bot": "http://bot-service:8009",
    }

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_ignore_empty=True
    )


settings = Settings()
