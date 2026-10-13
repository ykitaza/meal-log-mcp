import pytest

from domain.errors import InvalidGrant
from domain.refresh_token import REFRESH_TOKEN_TTL_SECONDS, RefreshToken, RefreshTokenFamily, RefreshTokenReused
from domain.values import ClientId, Subject
from tests.domain.test_aggregates import start

NOW = 1_000_000.0


def family():
    request = start().authenticate(Subject("user-1"))
    _, code = request.approve("code-1", NOW + 60)
    return RefreshTokenFamily.start("fam", code, "secret-1", NOW)


def test_系列は秘密の値をハッシュでだけ覚える():
    fam, token = family()
    assert str(token) == "fam.secret-1"
    assert "secret-1" not in fam.current_hash


def test_ローテーションすると新しい値になり期限が延びる():
    fam, token = family()
    rotated, new = fam.rotate(token, fam.client_id, None, "secret-2", NOW + 100)
    assert str(new) == "fam.secret-2"
    assert rotated.expires_at == NOW + 100 + REFRESH_TOKEN_TTL_SECONDS
    rotated.rotate(new, fam.client_id, None, "secret-3", NOW + 200)  # 新しいものは使える


def test_古い値を使うと再使用として断る():
    fam, token = family()
    rotated, _ = fam.rotate(token, fam.client_id, None, "secret-2", NOW)
    with pytest.raises(RefreshTokenReused):
        rotated.rotate(token, fam.client_id, None, "secret-3", NOW)


def test_期限切れと別のクライアントは断る():
    fam, token = family()
    with pytest.raises(InvalidGrant):
        fam.rotate(token, fam.client_id, None, "s", NOW + REFRESH_TOKEN_TTL_SECONDS)
    with pytest.raises(InvalidGrant):
        fam.rotate(token, ClientId("https://other.example/metadata.json"), None, "s", NOW)


@pytest.mark.parametrize("value", ["", "fam", "fam.", ".secret"])
def test_形が正しくない値は断る(value):
    with pytest.raises(InvalidGrant):
        RefreshToken.parse(value)
