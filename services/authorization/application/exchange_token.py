import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from domain.errors import InvalidGrant
from domain.ports import AccessTokenIssuer, AuthorizationCodeRepository, RefreshTokenFamilyRepository
from domain.refresh_token import REFRESH_TOKEN_TTL_SECONDS, RefreshToken, RefreshTokenFamily, RefreshTokenReused
from domain.values import ClientId, RedirectUri, ResourceIndicator

SecretFactory = Callable[[], str]


def new_secret() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class TokenCommand:
    """/token（grant_type=authorization_code）に届いた値。"""

    code: str
    redirect_uri: str
    client_id: str
    code_verifier: str
    resource: str | None


@dataclass(frozen=True)
class RefreshCommand:
    """/token（grant_type=refresh_token）に届いた値。"""

    refresh_token: str
    client_id: str
    resource: str | None


def _token_response(access_token: str, expires_in: int, refresh_token: RefreshToken, scope: str) -> dict:
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "refresh_token": str(refresh_token),
        "scope": scope,
    }


class ExchangeToken:
    """/token：認可コードを1回だけアクセストークンとリフレッシュトークンに引き換える。"""

    def __init__(
        self,
        codes: AuthorizationCodeRepository,
        families: RefreshTokenFamilyRepository,
        token_issuer: AccessTokenIssuer,
        clock: Callable[[], float] = time.time,
        new_secret: SecretFactory = new_secret,
    ):
        self.codes, self.families, self.token_issuer = codes, families, token_issuer
        self.clock, self.new_secret = clock, new_secret

    async def execute(self, cmd: TokenCommand) -> dict:
        code = await self.codes.take(cmd.code)
        if code is None:
            raise InvalidGrant("認可コードが無効か、使用済みです")
        now = self.clock()
        code.redeem(
            client_id=ClientId(cmd.client_id),
            redirect_uri=RedirectUri(cmd.redirect_uri),
            code_verifier=cmd.code_verifier,
            resource=ResourceIndicator(cmd.resource) if cmd.resource else None,
            now=now,
        )
        family, refresh_token = RefreshTokenFamily.start(self.new_secret(), code, self.new_secret(), now)
        await self.families.save(family, REFRESH_TOKEN_TTL_SECONDS)
        access_token, expires_in = self.token_issuer.issue(
            code.subject, code.client_id, code.scope, code.resource, family.id, int(now))
        return _token_response(access_token, expires_in, refresh_token, str(code.scope))


class RefreshAccessToken:
    """/token：リフレッシュトークンで、新しいアクセストークンとリフレッシュトークンを発行する（ローテーション）。"""

    def __init__(
        self,
        families: RefreshTokenFamilyRepository,
        token_issuer: AccessTokenIssuer,
        clock: Callable[[], float] = time.time,
        new_secret: SecretFactory = new_secret,
    ):
        self.families, self.token_issuer = families, token_issuer
        self.clock, self.new_secret = clock, new_secret

    async def execute(self, cmd: RefreshCommand) -> dict:
        presented = RefreshToken.parse(cmd.refresh_token)
        family = await self.families.get(presented.family_id)
        if family is None:
            raise InvalidGrant("リフレッシュトークンが無効です")
        now = self.clock()
        try:
            family, refresh_token = family.rotate(
                presented,
                client_id=ClientId(cmd.client_id),
                resource=ResourceIndicator(cmd.resource) if cmd.resource else None,
                new_secret=self.new_secret(),
                now=now,
            )
        except RefreshTokenReused:
            await self.families.delete(family.id)  # 盗まれた可能性があるので、系列ごと無効にする
            raise
        await self.families.save(family, REFRESH_TOKEN_TTL_SECONDS)
        access_token, expires_in = self.token_issuer.issue(
            family.subject, family.client_id, family.scope, family.resource, family.id, int(now))
        return _token_response(access_token, expires_in, refresh_token, str(family.scope))
