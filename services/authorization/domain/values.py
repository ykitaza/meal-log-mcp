"""値オブジェクト。中身で比べ、作るときにルールを確かめる。"""

import base64
import hashlib
from dataclasses import dataclass
from urllib.parse import urlsplit

from domain.errors import ClientRejected, InvalidRequest, InvalidScope

LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}


@dataclass(frozen=True)
class ClientId:
    """CIMD：クライアントの情報を書いた文書の URL。"""

    value: str

    def __post_init__(self):
        url = urlsplit(self.value)
        # 本来は https だけを認める。勉強用に、自分のPCの中（localhost）だけは http も認める
        if not (url.scheme == "https" or (url.scheme == "http" and url.hostname in LOOPBACK_HOSTS)):
            raise ClientRejected("client_id は https の URL である必要があります")
        if url.path in ("", "/") or url.fragment or url.username or url.password:
            raise ClientRejected("client_id の URL の形式が正しくありません")

    @property
    def host(self) -> str:
        """同意画面に出すドメイン。client_name は偽れるので、こちらも並べて出す。"""
        return urlsplit(self.value).netloc


@dataclass(frozen=True)
class RedirectUri:
    value: str

    def matches(self, registered: "RedirectUri") -> bool:
        if self.value == registered.value:
            return True
        # RFC 8252：自分のPCで動くアプリの戻り先（localhost）は、ポート番号を毎回変えてよい。
        # そのため localhost の http に限り、ポート番号以外が一致すれば認める
        url, reg = urlsplit(self.value), urlsplit(registered.value)
        if url.scheme != "http" or url.hostname not in LOOPBACK_HOSTS:
            return False
        return (url.scheme, url.hostname, url.path, url.query) == (reg.scheme, reg.hostname, reg.path, reg.query)


@dataclass(frozen=True)
class CodeChallenge:
    """PKCE：/authorize で受け取る、合言葉（code_verifier）の S256 ハッシュ。"""

    value: str

    @classmethod
    def from_request(cls, code_challenge: str | None, method: str | None) -> "CodeChallenge":
        if not code_challenge or method != "S256":
            raise InvalidRequest("PKCE（code_challenge_method=S256）が必要です")
        return cls(code_challenge)

    def verify(self, code_verifier: str) -> bool:
        digest = hashlib.sha256(code_verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode() == self.value


@dataclass(frozen=True)
class Scope:
    values: tuple[str, ...]

    @classmethod
    def parse(cls, scope: str | None) -> "Scope":
        return cls(tuple((scope or "").split()))

    def __str__(self) -> str:
        return " ".join(self.values)


@dataclass(frozen=True)
class ResourceIndicator:
    """RFC 8707：どのリソースサーバー宛てのトークンか。アクセストークンの aud になる。"""

    value: str


@dataclass(frozen=True)
class ResourceServer:
    """認可APIが知っているリソースサーバーと、そこで使える scope。"""

    indicator: ResourceIndicator
    scopes: Scope

    def grant(self, requested: Scope) -> Scope:
        """求められた scope のうち、このリソースサーバーで使えるものだけを許す（RFC 6749 3.3 で狭めてよい）。

        何も求められなければ、使える scope をすべて許す。
        """
        if not requested.values:
            return self.scopes
        granted = tuple(s for s in requested.values if s in self.scopes.values)
        if not granted:
            raise InvalidScope(f"このリソースサーバーで使える scope は {self.scopes} です")
        return Scope(granted)


@dataclass(frozen=True)
class Subject:
    """本人。本人確認コンテキスト（Cognito）から受け取った sub とメールアドレス。"""

    id: str
    email: str = ""
