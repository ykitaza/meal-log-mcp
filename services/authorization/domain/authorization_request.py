from dataclasses import dataclass, field, replace
from enum import Enum

from domain.authorization_code import AuthorizationCode
from domain.client import Client
from domain.errors import ClientRejected, InvalidRequest, InvalidTarget, UnsupportedResponseType
from domain.values import ClientId, CodeChallenge, RedirectUri, ResourceIndicator, ResourceServer, Scope, Subject


class Status(Enum):
    AWAITING_LOGIN = "awaiting_login"  # 本人確認（Cognito でのログイン）待ち
    AWAITING_CONSENT = "awaiting_consent"  # 本人の同意待ち
    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True)
class AuthorizationRequest:
    """集約：OAuth クライアントからの認可リクエスト。

    本人確認待ち → 同意待ち → 許可／拒否 の順にだけ進む。
    """

    id: str
    client_id: ClientId
    client_name: str
    redirect_uri: RedirectUri
    client_state: str | None  # クライアントが送ってきた state。戻すときにそのまま返す
    scope: Scope
    code_challenge: CodeChallenge
    resource: ResourceIndicator
    status: Status = Status.AWAITING_LOGIN
    subject: Subject | None = field(default=None)

    @classmethod
    def start(
        cls,
        id: str,
        client: Client,
        redirect_uri: RedirectUri,
        client_state: str | None,
        response_type: str | None,
        scope: Scope,
        code_challenge: str | None,
        code_challenge_method: str | None,
        resource: ResourceIndicator,
        allowed_resources: list[ResourceServer],
    ) -> "AuthorizationRequest":
        # redirect_uri が確かめられないうちは、そこへ返さない（攻撃者の URL かもしれないため）
        if not client.allows_redirect(redirect_uri):
            raise ClientRejected("redirect_uri がクライアントのメタデータと一致しません")
        # ここから先のエラーは、クライアントの redirect_uri へ返してよい
        if response_type != "code":
            raise UnsupportedResponseType("response_type は code だけに対応しています")
        challenge = CodeChallenge.from_request(code_challenge, code_challenge_method)
        server = next((s for s in allowed_resources if s.indicator == resource), None)
        if server is None:
            raise InvalidTarget("知らないリソースサーバーです")
        return cls(id, client.id, client.name, redirect_uri, client_state, server.grant(scope), challenge, resource)

    def authenticate(self, subject: Subject) -> "AuthorizationRequest":
        """本人確認が済んだ。本人を結び付けて、同意待ちにする。"""
        self._require(Status.AWAITING_LOGIN)
        return replace(self, status=Status.AWAITING_CONSENT, subject=subject)

    def restart_login(self) -> "AuthorizationRequest":
        """同意画面で「別のアカウントで入り直す」を選んだ。本人を外し、本人確認待ちに戻す。"""
        self._require(Status.AWAITING_CONSENT)
        return replace(self, status=Status.AWAITING_LOGIN, subject=None)

    def approve(self, code_value: str, expires_at: float) -> tuple["AuthorizationRequest", AuthorizationCode]:
        """本人が許可した。認可コードを発行する。"""
        self._require(Status.AWAITING_CONSENT)
        code = AuthorizationCode(
            value=code_value,
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            code_challenge=self.code_challenge,
            resource=self.resource,
            subject=self.subject,
            expires_at=expires_at,
        )
        return replace(self, status=Status.APPROVED), code

    def deny(self) -> "AuthorizationRequest":
        self._require(Status.AWAITING_CONSENT)
        return replace(self, status=Status.DENIED)

    def _require(self, status: Status) -> None:
        if self.status != status:
            raise InvalidRequest(f"認可リクエストが {status.value} の状態ではありません（今は {self.status.value}）")
