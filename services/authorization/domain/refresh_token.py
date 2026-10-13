import hashlib
import hmac
from dataclasses import dataclass, replace

from domain.authorization_code import AuthorizationCode
from domain.errors import InvalidGrant, InvalidTarget
from domain.values import ClientId, ResourceIndicator, Scope, Subject

REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60  # 使うたびに、ここから数え直す


class RefreshTokenReused(InvalidGrant):
    """ローテーションで古くなったリフレッシュトークンが使われた。盗まれた可能性があるので、系列ごと無効にする。"""


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


@dataclass(frozen=True)
class RefreshToken:
    """値：クライアントに渡すリフレッシュトークン。「<系列ID>.<ランダムな値>」の形。"""

    family_id: str
    secret: str

    @classmethod
    def parse(cls, value: str) -> "RefreshToken":
        family_id, dot, secret = value.partition(".")
        if not (family_id and dot and secret):
            raise InvalidGrant("リフレッシュトークンの形が正しくありません")
        return cls(family_id, secret)

    def __str__(self) -> str:
        return f"{self.family_id}.{self.secret}"


@dataclass(frozen=True)
class RefreshTokenFamily:
    """集約：リフレッシュトークンの系列。ログインして同意するたびに1つでき、ローテーションしても続く。

    覚えているのは最新のリフレッシュトークンのハッシュだけ（DB が漏れても、そのままでは使えない）。
    """

    id: str
    client_id: ClientId
    subject: Subject
    scope: Scope
    resource: ResourceIndicator
    current_hash: str
    expires_at: float

    @classmethod
    def start(
        cls, id: str, code: AuthorizationCode, secret: str, now: float,
    ) -> tuple["RefreshTokenFamily", RefreshToken]:
        """認可コードを引き換えたときに、系列を始める。"""
        family = cls(id, code.client_id, code.subject, code.scope, code.resource, _hash(secret),
                     now + REFRESH_TOKEN_TTL_SECONDS)
        return family, RefreshToken(id, secret)

    def rotate(
        self,
        presented: RefreshToken,
        client_id: ClientId,
        resource: ResourceIndicator | None,
        new_secret: str,
        now: float,
    ) -> tuple["RefreshTokenFamily", RefreshToken]:
        """リフレッシュトークンを使った。新しいものに替え、期限も延ばす。"""
        if self.expires_at <= now:
            raise InvalidGrant("リフレッシュトークンの期限が切れています")
        # 最新のものでなければ、すでに使われた古いもの（盗まれて使われた可能性がある）
        if not hmac.compare_digest(_hash(presented.secret), self.current_hash):
            raise RefreshTokenReused("このリフレッシュトークンはすでに使われています")
        if client_id != self.client_id:
            raise InvalidGrant("client_id がリフレッシュトークンと一致しません")
        if resource is not None and resource != self.resource:
            raise InvalidTarget("resource がリフレッシュトークンと一致しません")
        rotated = replace(self, current_hash=_hash(new_secret), expires_at=now + REFRESH_TOKEN_TTL_SECONDS)
        return rotated, RefreshToken(self.id, new_secret)
