from config import settings


def check_public_path(request_path: str) -> bool:
    """
    Возвращает True на публичные ручки.
    """
    if any(
        request_path.startswith(public_path) for public_path in settings.public_paths
    ):
        return True
    # TODO: Временное решение для тест контура. Доработать.
    if request_path.endswith(("openapi.json", "docs", "redoc", "health")):
        return True
