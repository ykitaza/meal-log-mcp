from application.start_authorization import REQUEST_TTL_SECONDS
from domain.errors import InvalidRequest
from domain.ports import AuthorizationRequestRepository


class RestartLogin:
    """同意画面で「別のアカウントで入り直す」を選んだ。同じ認可リクエストのまま、本人確認からやり直す。"""

    def __init__(self, requests: AuthorizationRequestRepository):
        self.requests = requests

    async def execute(self, request_id: str) -> None:
        request = await self.requests.get(request_id)
        if request is None:
            raise InvalidRequest("認可リクエストが見つかりません（期限切れの可能性があります）")
        await self.requests.save(request.restart_login(), REQUEST_TTL_SECONDS)
