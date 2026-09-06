from config import settings


def _path_matches(path: str, allowed_path: str) -> bool:
    normalized = allowed_path.rstrip("/")
    return path == normalized or path.startswith(f"{normalized}/")


def check_public_path(request_path: str) -> bool:
    """
    Возвращает True на публичные ручки.
    """
    if any(
        _path_matches(request_path, public_path)
        for public_path in settings.public_paths
    ):
        return True
    if any(
        _path_matches(request_path, cacheable_path)
        for cacheable_path in settings.cacheable_paths
    ):
        return True
    # TODO: Временное решение для тест контура. Доработать.
    return request_path.endswith(("openapi.json", "docs", "redoc", "health"))
