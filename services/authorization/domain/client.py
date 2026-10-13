from dataclasses import dataclass

from domain.values import ClientId, RedirectUri


@dataclass(frozen=True)
class Client:
    """OAuth クライアント。CIMD の文書から作る（事前登録はしない）。"""

    id: ClientId
    name: str
    redirect_uris: tuple[RedirectUri, ...]

    def allows_redirect(self, redirect_uri: RedirectUri) -> bool:
        return any(redirect_uri.matches(registered) for registered in self.redirect_uris)
