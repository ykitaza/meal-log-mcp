import json
import secrets

import jwt
from cryptography.hazmat.primitives import serialization

from domain.values import ClientId, ResourceIndicator, Scope, Subject

KEY_ID = "authz-key-1"


class JwtAccessTokenIssuer:
    """AccessTokenIssuer の実装。認可API自身の鍵で署名した JWT（RFC 9068 の形式）を発行する。"""

    # 5分：取り消し（ログアウト）しても、発行済みのアクセストークンは期限まで使えてしまうため短くする
    def __init__(self, private_key_pem: str, issuer: str, ttl_seconds: int = 300):
        self.private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
        self.issuer, self.ttl_seconds = issuer, ttl_seconds
        public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key()))
        self.public_jwk = {**public_jwk, "kid": KEY_ID, "use": "sig", "alg": "RS256"}

    def issue(
        self, subject: Subject, client_id: ClientId, scope: Scope, resource: ResourceIndicator, session_id: str,
        now: int,
    ) -> tuple[str, int]:
        claims = {
            "iss": self.issuer,  # 発行者：認可API
            "sub": subject.id,  # 本人：本人確認コンテキスト（Cognito）の sub
            "aud": resource.value,  # 宛先：クライアントが resource で求めたリソースサーバー
            "client_id": client_id.value,  # 誰に渡したか
            "scope": str(scope),  # 何を許したか
            "sid": session_id,  # どの連携（リフレッシュトークンの系列）から発行したか
            "iat": now,
            "exp": now + self.ttl_seconds,
            "jti": secrets.token_urlsafe(16),
        }
        token = jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": KEY_ID, "typ": "at+jwt"})
        return token, self.ttl_seconds

    def read(self, token: str) -> dict | None:
        try:
            # 署名と iss だけを確かめる。宛先（aud）と期限は問わない（取り消しに使うため）
            return jwt.decode(token, self.private_key.public_key(), algorithms=["RS256"], issuer=self.issuer,
                              options={"verify_aud": False, "verify_exp": False})
        except jwt.PyJWTError:
            return None

    def jwks(self) -> dict:
        # 公開鍵だけを公開する。リソースサーバーはこれで署名を検証する
        return {"keys": [self.public_jwk]}
