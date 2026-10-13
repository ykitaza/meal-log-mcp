import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from application.start_authorization import REQUEST_TTL_SECONDS
from domain.errors import AccessDenied, InvalidRequest
from domain.ports import AuthorizationCodeRepository, AuthorizationRequestRepository

CODE_TTL_SECONDS = 60


@dataclass(frozen=True)
class AuthorizationResponse:
    """クライアントの redirect_uri へ返す内容。"""

    redirect_uri: str
    params: dict[str, str]


class DecideConsent:
    """本人の同意の結果を受け取る。許可なら認可コードを発行し、拒否なら access_denied を返す。"""

    def __init__(
        self,
        requests: AuthorizationRequestRepository,
        codes: AuthorizationCodeRepository,
        issuer: str,
        new_code: Callable[[], str] = lambda: secrets.token_urlsafe(32),
        clock: Callable[[], float] = time.time,
    ):
        self.requests, self.codes, self.issuer = requests, codes, issuer
        self.new_code, self.clock = new_code, clock

    async def execute(self, request_id: str, approved: bool) -> AuthorizationResponse:
        request = await self.requests.get(request_id)
        if request is None:
            raise InvalidRequest("認可リクエストが見つかりません（期限切れの可能性があります）")

        # iss は「どの認可サーバーからの応答か」（RFC 9207）
        params = {"iss": self.issuer}
        if approved:
            request, code = request.approve(self.new_code(), self.clock() + CODE_TTL_SECONDS)
            await self.codes.save(code, CODE_TTL_SECONDS)
            params["code"] = code.value
        else:
            request = request.deny()
            params["error"] = AccessDenied.code
        await self.requests.save(request, REQUEST_TTL_SECONDS)
        if request.client_state:
            params["state"] = request.client_state
        return AuthorizationResponse(request.redirect_uri.value, params)
