"""アクセストークンの検証を、9通りのトークンで確かめる（以前 api/ で行ったテストの移植）。"""

import asyncio
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from infrastructure.access_token_verifier import AuthzApiTokenVerifier

ISSUER = "https://authz.example"
RESOURCE = "https://mcp.example/mcp"
REAL_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
FAKE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


async def stub_jwks() -> dict:
    """JWKS の取得の代わりに、認可APIの本物の公開鍵を返す。"""
    return {"keys": [{**RSAAlgorithm.to_jwk(REAL_KEY.public_key(), as_dict=True), "kid": "k", "alg": "RS256"}]}


def token(key=REAL_KEY, headers=None, **overrides):
    now = int(time.time())
    claims = {"iss": ISSUER, "sub": "user-1", "aud": RESOURCE, "client_id": "c", "scope": "read",
              "iat": now, "exp": now + 60, **overrides}
    return jwt.encode(claims, key, algorithm="RS256", headers=headers or {"kid": "k", "typ": "at+jwt"})


def verify(t):
    return asyncio.run(AuthzApiTokenVerifier(ISSUER, RESOURCE, fetch_jwks=stub_jwks).verify_token(t))


def test_accepts_valid_token():
    result = verify(token())
    assert (result.subject, result.scopes, result.client_id) == ("user-1", ["read"], "c")


@pytest.mark.parametrize("bad", [
    "abc.def.ghi",  # でたらめ
    token(key=FAKE_KEY),  # 別の鍵で署名（なりすまし）
    token(iss="https://evil.example"),
    token(aud="https://other.example/mcp"),  # 別のリソースサーバー宛て
    token(iat=int(time.time()) - 700, exp=int(time.time()) - 100),  # 期限切れ
    token(headers={"kid": "k"}),  # typ が at+jwt でない（IDトークンの取り違え）
])
def test_rejects_invalid_tokens(bad):
    assert verify(bad) is None
