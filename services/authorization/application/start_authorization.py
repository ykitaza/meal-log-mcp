import secrets
from collections.abc import Callable
from dataclasses import dataclass

from domain.authorization_request import AuthorizationRequest
from domain.errors import InvalidTarget, OAuthError
from domain.ports import AuthorizationRequestRepository, ClientDirectory
from domain.values import ClientId, RedirectUri, ResourceIndicator, ResourceServer, Scope

REQUEST_TTL_SECONDS = 600


@dataclass(frozen=True)
class AuthorizeCommand:
    """/authorize に届いた値。"""

    client_id: str
    redirect_uri: str
    response_type: str | None
    state: str | None
    scope: str | None
    code_challenge: str | None
    code_challenge_method: str | None
    resource: str | None


class RedirectableError(Exception):
    """クライアントの redirect_uri へ error として返すエラー。"""

    def __init__(self, redirect_uri: str, state: str | None, error: OAuthError):
        super().__init__(error.description)
        self.redirect_uri, self.state, self.error = redirect_uri, state, error


class StartAuthorization:
    """/authorize：クライアントの要求を確かめて保存する。このあと本人確認（ログイン）へ進む。"""

    def __init__(
        self,
        clients: ClientDirectory,
        requests: AuthorizationRequestRepository,
        allowed_resources: list[ResourceServer],
        new_id: Callable[[], str] = lambda: secrets.token_urlsafe(16),
    ):
        self.clients, self.requests = clients, requests
        self.allowed_resources, self.new_id = allowed_resources, new_id

    async def execute(self, cmd: AuthorizeCommand) -> str:
        # CIMD：client_id の URL から文書を取りに行く。確かめられなければ ClientRejected（エラー画面）
        client = await self.clients.find(ClientId(cmd.client_id))
        redirect_uri = RedirectUri(cmd.redirect_uri)
        try:
            resource = self._resource(cmd.resource)
            request = AuthorizationRequest.start(
                id=self.new_id(),
                client=client,
                redirect_uri=redirect_uri,
                client_state=cmd.state,
                response_type=cmd.response_type,
                scope=Scope.parse(cmd.scope),
                code_challenge=cmd.code_challenge,
                code_challenge_method=cmd.code_challenge_method,
                resource=resource,
                allowed_resources=self.allowed_resources,
            )
        except OAuthError as e:
            raise RedirectableError(redirect_uri.value, cmd.state, e)
        await self.requests.save(request, REQUEST_TTL_SECONDS)
        return request.id

    def _resource(self, resource: str | None) -> ResourceIndicator:
        if resource:
            return ResourceIndicator(resource)
        # resource を送ってこなければ、リソースサーバーが1つのときに限りそこ宛てにする（2つ以上だと決められない）
        if len(self.allowed_resources) == 1:
            return self.allowed_resources[0].indicator
        raise InvalidTarget("resource（どのリソースサーバー宛てか）を指定してください")
