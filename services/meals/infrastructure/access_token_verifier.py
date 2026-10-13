from collections.abc import Awaitable, Callable

import httpx2
import jwt
from mcp.server.auth.provider import AccessToken

JwksFetcher = Callable[[], Awaitable[dict]]


class AuthzApiTokenVerifier:
    """MCP SDK の TokenVerifier の実装。認可APIが発行したアクセストークンを検証する。

    認可コンテキストとの約束（公開された形）は、アクセストークンの JWT だけ。
    公開鍵（JWKS）は非同期の HTTP で取る（スレッドを使わないので、Lambda でも Cloudflare Workers でも動く）。
    HTTP クライアントは MCP SDK と同じ httpx2（Workers の上では fetch を使う版に切り替わる）。
    """

    def __init__(self, trusted_issuer: str, resource_url: str, fetch_jwks: JwksFetcher | None = None):
        self.trusted_issuer, self.resource_url = trusted_issuer, resource_url
        self.fetch_jwks = fetch_jwks or self._fetch_jwks
        self.keys: dict[str, jwt.PyJWK] = {}  # kid → 公開鍵。知らない kid が来たときだけ取り直す

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
            # IDトークンなどを取り違えて送ってきていないか（RFC 9068 のアクセストークンは typ が at+jwt）
            if header.get("typ") != "at+jwt":
                return None
            key = await self._key(header.get("kid"))
            if key is None:
                return None
            # 署名・iss（信じる発行者か）・aud（自分宛てか）・exp（期限内か）を検証する
            claims = jwt.decode(
                token, key, algorithms=["RS256"], issuer=self.trusted_issuer, audience=self.resource_url)
        except (jwt.PyJWTError, httpx2.HTTPError):
            return None  # SDK が 401 と resource_metadata を返す
        return AccessToken(
            token=token,
            client_id=claims["client_id"],
            scopes=claims.get("scope", "").split(),
            expires_at=claims["exp"],
            resource=self.resource_url,
            subject=claims["sub"],
            claims=claims,
        )

    async def _key(self, kid: str | None) -> jwt.PyJWK | None:
        if kid not in self.keys:  # 鍵が替わった（または初回）
            jwks = jwt.PyJWKSet.from_dict(await self.fetch_jwks())
            self.keys = {k.key_id: k for k in jwks.keys}
        return self.keys.get(kid)

    async def _fetch_jwks(self) -> dict:
        async with httpx2.AsyncClient(timeout=5) as client:
            res = await client.get(f"{self.trusted_issuer}/.well-known/jwks.json")
            res.raise_for_status()
            return res.json()
