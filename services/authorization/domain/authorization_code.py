from dataclasses import dataclass

from domain.errors import InvalidGrant, InvalidTarget
from domain.values import ClientId, CodeChallenge, RedirectUri, ResourceIndicator, Scope, Subject


@dataclass(frozen=True)
class AuthorizationCode:
    """集約：認可コード。/token で1回だけアクセストークンに引き換えられる。

    1回だけであることは、リポジトリの take（取り出すと同時に消す）で守る。
    """

    value: str
    client_id: ClientId
    redirect_uri: RedirectUri
    scope: Scope
    code_challenge: CodeChallenge
    resource: ResourceIndicator
    subject: Subject
    expires_at: float

    def redeem(
        self,
        client_id: ClientId,
        redirect_uri: RedirectUri,
        code_verifier: str,
        resource: ResourceIndicator | None,
        now: float,
    ) -> None:
        if self.expires_at <= now:
            raise InvalidGrant("認可コードの期限が切れています")
        # 認可コードを発行したときと同じクライアント、同じ redirect_uri か
        if client_id != self.client_id or redirect_uri.value != self.redirect_uri.value:
            raise InvalidGrant("client_id または redirect_uri が認可コードと一致しません")
        # /token でも resource を送ってきたなら、/authorize のときと同じか（RFC 8707）
        if resource is not None and resource != self.resource:
            raise InvalidTarget("resource が認可コードと一致しません")
        # PKCE：合言葉のハッシュが、/authorize で受け取った code_challenge と一致するか
        if not self.code_challenge.verify(code_verifier):
            raise InvalidGrant("code_verifier が一致しません")
