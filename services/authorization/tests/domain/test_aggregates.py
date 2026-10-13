import pytest

from domain.authorization_request import AuthorizationRequest, Status
from domain.client import Client
from domain.errors import (
    ClientRejected, InvalidGrant, InvalidRequest, InvalidScope, InvalidTarget, UnsupportedResponseType)
from domain.values import ClientId, RedirectUri, ResourceIndicator, ResourceServer, Scope, Subject

CLIENT = Client(
    id=ClientId("https://client.example/metadata.json"),
    name="Example",
    redirect_uris=(RedirectUri("https://client.example/callback"),),
)
MCP = ResourceIndicator("https://mcp.example/mcp")
MEALS = ResourceIndicator("https://meals.example/mcp")
SERVERS = [
    ResourceServer(MCP, Scope(("read",))),
    ResourceServer(MEALS, Scope(("meals:read", "meals:write"))),
]
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def start(**overrides) -> AuthorizationRequest:
    args = dict(
        id="req-1", client=CLIENT, redirect_uri=RedirectUri("https://client.example/callback"),
        client_state="xyz", response_type="code", scope=Scope(("read",)),
        code_challenge=CHALLENGE, code_challenge_method="S256", resource=MCP, allowed_resources=SERVERS,
    )
    return AuthorizationRequest.start(**{**args, **overrides})


def test_start_rejects_unregistered_redirect_uri():
    with pytest.raises(ClientRejected):
        start(redirect_uri=RedirectUri("https://evil.example/callback"))


@pytest.mark.parametrize("overrides, error", [
    ({"response_type": "token"}, UnsupportedResponseType),
    ({"code_challenge": None}, InvalidRequest),
    ({"resource": ResourceIndicator("https://other.example/mcp")}, InvalidTarget),
    ({"scope": Scope(("meals:write",))}, InvalidScope),  # そのリソースサーバーでは使えない scope だけ
])
def test_start_rejects_invalid_requests(overrides, error):
    with pytest.raises(error):
        start(**overrides)


@pytest.mark.parametrize("resource, requested, granted", [
    (MEALS, (), ("meals:read", "meals:write")),  # 求めなければ、そのリソースサーバーの scope をすべて
    (MEALS, ("meals:read",), ("meals:read",)),
    (MEALS, ("read", "meals:read", "meals:write"), ("meals:read", "meals:write")),  # 使えないものは外す
    (MCP, ("read", "meals:write"), ("read",)),
])
def test_start_grants_only_scopes_of_the_resource(resource, requested, granted):
    assert start(resource=resource, scope=Scope(requested)).scope == Scope(granted)


def test_request_moves_from_login_to_consent_to_approved():
    request = start()
    assert request.status == Status.AWAITING_LOGIN
    request = request.authenticate(Subject("user-1", "u@example.com"))
    assert request.status == Status.AWAITING_CONSENT
    request, code = request.approve("code-1", expires_at=1060)
    assert request.status == Status.APPROVED
    assert (code.subject.id, code.resource, code.client_id) == ("user-1", MCP, CLIENT.id)


def test_restart_login_goes_back_to_awaiting_login():
    request = start().authenticate(Subject("wrong-user")).restart_login()
    assert (request.status, request.subject) == (Status.AWAITING_LOGIN, None)
    with pytest.raises(InvalidRequest):  # 本人確認の前には戻せない
        start().restart_login()


def test_cannot_approve_before_login():
    with pytest.raises(InvalidRequest):
        start().approve("code-1", expires_at=1060)


def test_cannot_approve_twice():
    request, _ = start().authenticate(Subject("user-1")).approve("code-1", expires_at=1060)
    with pytest.raises(InvalidRequest):
        request.approve("code-2", expires_at=1060)


def issued_code():
    _, code = start().authenticate(Subject("user-1")).approve("code-1", expires_at=1060)
    return code


def redeem(code, **overrides):
    args = dict(client_id=CLIENT.id, redirect_uri=RedirectUri("https://client.example/callback"),
                code_verifier=VERIFIER, resource=MCP, now=1000)
    code.redeem(**{**args, **overrides})


def test_code_redeems_with_matching_values():
    redeem(issued_code())


@pytest.mark.parametrize("overrides, error", [
    ({"now": 1060}, InvalidGrant),  # 期限切れ
    ({"client_id": ClientId("https://other.example/metadata.json")}, InvalidGrant),
    ({"redirect_uri": RedirectUri("https://client.example/other")}, InvalidGrant),
    ({"code_verifier": "wrong"}, InvalidGrant),  # PKCE
    ({"resource": ResourceIndicator("https://other.example/mcp")}, InvalidTarget),
])
def test_code_rejects_mismatches(overrides, error):
    with pytest.raises(error):
        redeem(issued_code(), **overrides)
