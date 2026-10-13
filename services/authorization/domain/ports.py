"""ポート：ドメインが外に求める働きの型。実装（アダプター）は infrastructure/ に置く。

待ち時間があるもの（DB、HTTP）は async にする。AccessTokenIssuer は署名の計算だけなので同期のまま。
"""

from typing import Protocol

from domain.authorization_code import AuthorizationCode
from domain.authorization_request import AuthorizationRequest
from domain.client import Client
from domain.refresh_token import RefreshTokenFamily
from domain.values import ClientId, ResourceIndicator, Scope, Subject


class AuthorizationRequestRepository(Protocol):
    async def save(self, request: AuthorizationRequest, ttl_seconds: int) -> None: ...

    async def get(self, request_id: str) -> AuthorizationRequest | None: ...


class AuthorizationCodeRepository(Protocol):
    async def save(self, code: AuthorizationCode, ttl_seconds: int) -> None: ...

    async def take(self, value: str) -> AuthorizationCode | None:
        """取り出すと同時に消す。認可コードを2回使わせないため。"""
        ...


class RefreshTokenFamilyRepository(Protocol):
    async def save(self, family: RefreshTokenFamily, ttl_seconds: int) -> None: ...

    async def get(self, family_id: str) -> RefreshTokenFamily | None: ...

    async def delete(self, family_id: str) -> None: ...


class ClientDirectory(Protocol):
    async def find(self, client_id: ClientId) -> Client:
        """クライアントを得る。確かめられなければ ClientRejected。"""
        ...


class AccessTokenIssuer(Protocol):
    def issue(
        self, subject: Subject, client_id: ClientId, scope: Scope, resource: ResourceIndicator, session_id: str,
        now: int,
    ) -> tuple[str, int]:
        """アクセストークンと、その有効秒数を返す。session_id はリフレッシュトークンの系列 ID（取り消しに使う）。"""
        ...

    def read(self, token: str) -> dict | None:
        """自分が発行したアクセストークンなら、その中身（クレーム）を返す。期限切れでもよい（取り消しに使うため）。"""
        ...

    def jwks(self) -> dict:
        """署名を検証するための公開鍵（JWKS）。"""
        ...
