from dataclasses import dataclass

from application.start_authorization import REQUEST_TTL_SECONDS
from domain.errors import InvalidRequest
from domain.ports import AuthorizationRequestRepository
from domain.values import Subject


@dataclass(frozen=True)
class ConsentView:
    """同意画面に出す内容。"""

    client_name: str
    client_host: str
    email: str
    scopes: tuple[str, ...]


class CompleteLogin:
    """本人確認（ログイン）が済んだ認可リクエストに本人を結び付け、同意待ちにする。"""

    def __init__(self, requests: AuthorizationRequestRepository):
        self.requests = requests

    async def execute(self, request_id: str, subject: Subject) -> ConsentView:
        request = await self.requests.get(request_id)
        if request is None:
            raise InvalidRequest("認可リクエストが見つかりません（期限切れの可能性があります）")
        request = request.authenticate(subject)
        await self.requests.save(request, REQUEST_TTL_SECONDS)
        return ConsentView(request.client_name, request.client_id.host, subject.email, request.scope.values)
