"""認可コンテキストのエラー。OAuth のエラーコード（RFC 6749 など）をそのまま名前に使う。"""


class ClientRejected(Exception):
    """クライアントか redirect_uri を確かめられない。

    redirect_uri が攻撃者の URL かもしれないので、そこへは返さずにエラー画面を出す。
    """


class OAuthError(Exception):
    """クライアントに返してよい OAuth のエラー。"""

    code = "invalid_request"

    def __init__(self, description: str):
        super().__init__(description)
        self.description = description


class InvalidRequest(OAuthError):
    code = "invalid_request"


class UnsupportedResponseType(OAuthError):
    code = "unsupported_response_type"


class InvalidTarget(OAuthError):
    """RFC 8707：知らないリソースサーバー宛てのトークンを求められた。"""

    code = "invalid_target"


class InvalidScope(OAuthError):
    """そのリソースサーバーでは使えない scope だけを求められた。"""

    code = "invalid_scope"


class AccessDenied(OAuthError):
    code = "access_denied"


class InvalidGrant(OAuthError):
    """認可コードが無効・期限切れ・別のクライアント向け、または PKCE が一致しない。"""

    code = "invalid_grant"


class UnsupportedGrantType(OAuthError):
    code = "unsupported_grant_type"
