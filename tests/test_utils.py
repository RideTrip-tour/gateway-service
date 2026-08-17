import pytest

from app.utils.token import match_tokens


@pytest.mark.asyncio
async def test_match_token():
    expected_token = "TOKEN"
    actual_token = "TOKEN"

    assert await match_tokens(actual_token, expected_token)

    wrong_token = "Token"

    assert not await match_tokens(wrong_token, expected_token)
