from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret: str = "secret"
    auth_service_url: str = "http://auth:8000"
    redis_url: str = "redis://127.0.0.1:6379"
    redis_ttl: int = 300  # время жизни кеша по умолчанию
    rate_limit: int = 100  # запросов в минуту
    public_paths: list[str] = ["/docs", "/redoc"]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_ignore_empty=True
    )


settings = Settings()
