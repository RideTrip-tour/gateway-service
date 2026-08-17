import secrets


async def match_tokens(expected: str, actual: str) -> bool:
    """
    Сравнивает токены.
    """
    return secrets.compare_digest(
        actual,
        expected,
    )
