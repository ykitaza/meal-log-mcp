from domain.errors import InvalidGrant
from domain.ports import AccessTokenIssuer, RefreshTokenFamilyRepository
from domain.refresh_token import RefreshToken
from domain.values import ClientId


class RevokeToken:
    """/revoke（RFC 7009）：トークンを取り消す。リフレッシュトークンでもアクセストークンでも、その連携の系列ごと消す。

    知らないトークンや、別のクライアントのトークンでも、エラーにはせず何もしない（RFC 7009 2.2）。
    """

    def __init__(self, families: RefreshTokenFamilyRepository, token_issuer: AccessTokenIssuer):
        self.families, self.token_issuer = families, token_issuer

    async def execute(self, token: str, client_id: str) -> None:
        family_id = self._family_id(token)
        if family_id is None:
            return
        family = await self.families.get(family_id)
        if family is not None and family.client_id == ClientId(client_id):
            await self.families.delete(family.id)

    def _family_id(self, token: str) -> str | None:
        if token.count(".") == 1:  # リフレッシュトークン（系列ID.ランダムな値）
            try:
                return RefreshToken.parse(token).family_id
            except InvalidGrant:
                return None
        claims = self.token_issuer.read(token)  # アクセストークン（JWT）
        return claims.get("sid") if claims else None
