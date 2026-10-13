"""偽物のアダプター（メモリーのリポジトリ、決め打ちのクライアント）を差し込んで、ユースケースを通しで確かめる。"""

import jwt
import pytest

from application.complete_login import CompleteLogin
from application.decide_consent import DecideConsent
from application.exchange_token import ExchangeToken, RefreshAccessToken, RefreshCommand, TokenCommand
from application.restart_login import RestartLogin
from application.revoke_token import RevokeToken
from application.start_authorization import AuthorizeCommand, RedirectableError, StartAuthorization
from domain.client import Client
from domain.errors import ClientRejected, InvalidGrant, InvalidTarget
from domain.values import ClientId, RedirectUri, ResourceIndicator, ResourceServer, Scope, Subject
from infrastructure.jwt_access_token_issuer import JwtAccessTokenIssuer
from infrastructure.memory_repositories import (
    MemoryAuthorizationCodeRepository,
    MemoryAuthorizationRequestRepository,
    MemoryRefreshTokenFamilyRepository,
)
from infrastructure.settings import new_private_key_pem

ISSUER = "https://authz.example"
MCP = "https://mcp.example/mcp"
MEALS = "https://meals.example/mcp"
SERVERS = [
    ResourceServer(ResourceIndicator(MCP), Scope(("read",))),
    ResourceServer(ResourceIndicator(MEALS), Scope(("meals:read", "meals:write"))),
]
CLIENT_ID = "https://client.example/metadata.json"
REDIRECT = "https://client.example/callback"
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


class FakeClientDirectory:
    async def find(self, client_id: ClientId) -> Client:
        if client_id.value != CLIENT_ID:
            raise ClientRejected("unknown client")
        return Client(client_id, "Example", (RedirectUri(REDIRECT),))


@pytest.fixture
def app():
    requests, codes = MemoryAuthorizationRequestRepository(), MemoryAuthorizationCodeRepository()
    families = MemoryRefreshTokenFamilyRepository()
    issuer = JwtAccessTokenIssuer(new_private_key_pem(), ISSUER)
    return {
        "start": StartAuthorization(FakeClientDirectory(), requests, SERVERS),
        "login": CompleteLogin(requests),
        "consent": DecideConsent(requests, codes, ISSUER),
        "token": ExchangeToken(codes, families, issuer),
        "refresh": RefreshAccessToken(families, issuer),
        "revoke": RevokeToken(families, issuer),
        "restart": RestartLogin(requests),
        "issuer": issuer,
    }


def authorize(**overrides) -> AuthorizeCommand:
    args = dict(client_id=CLIENT_ID, redirect_uri=REDIRECT, response_type="code", state="xyz", scope="read",
                code_challenge=CHALLENGE, code_challenge_method="S256", resource=MCP)
    return AuthorizeCommand(**{**args, **overrides})


def token_command(code: str) -> TokenCommand:
    return TokenCommand(code, REDIRECT, CLIENT_ID, VERIFIER, MCP)


@pytest.mark.anyio
async def test_full_flow_issues_access_token_for_the_resource(app):
    request_id = await app["start"].execute(authorize())
    view = await app["login"].execute(request_id, Subject("user-1", "u@example.com"))
    assert (view.client_name, view.client_host, view.scopes) == ("Example", "client.example", ("read",))

    res = await app["consent"].execute(request_id, approved=True)
    assert res.redirect_uri == REDIRECT
    assert res.params["state"] == "xyz" and res.params["iss"] == ISSUER

    body = await app["token"].execute(token_command(res.params["code"]))
    key = jwt.PyJWK(app["issuer"].jwks()["keys"][0])
    claims = jwt.decode(body["access_token"], key, algorithms=["RS256"], audience=MCP, issuer=ISSUER)
    assert (claims["sub"], claims["client_id"], claims["scope"]) == ("user-1", CLIENT_ID, "read")


@pytest.mark.anyio
async def test_code_can_be_used_only_once(app):
    request_id = await app["start"].execute(authorize())
    await app["login"].execute(request_id, Subject("user-1"))
    code = (await app["consent"].execute(request_id, approved=True)).params["code"]
    await app["token"].execute(token_command(code))
    with pytest.raises(InvalidGrant):
        await app["token"].execute(token_command(code))


@pytest.mark.anyio
async def test_denied_consent_returns_access_denied(app):
    request_id = await app["start"].execute(authorize())
    await app["login"].execute(request_id, Subject("user-1"))
    res = await app["consent"].execute(request_id, approved=False)
    assert res.params == {"iss": ISSUER, "error": "access_denied", "state": "xyz"}


@pytest.mark.anyio
async def test_invalid_request_is_returned_to_the_client(app):
    with pytest.raises(RedirectableError) as e:
        await app["start"].execute(authorize(code_challenge=None))
    assert (e.value.redirect_uri, e.value.error.code) == (REDIRECT, "invalid_request")


@pytest.mark.anyio
async def test_unknown_client_is_not_redirected(app):
    with pytest.raises(ClientRejected):
        await app["start"].execute(authorize(client_id="https://evil.example/metadata.json"))


@pytest.mark.anyio
async def test_resource_is_required_when_there_are_two_resource_servers(app):
    with pytest.raises(RedirectableError) as e:
        await app["start"].execute(authorize(resource=None))
    assert e.value.error.code == "invalid_target"


@pytest.mark.anyio
async def test_meals_token_carries_only_meals_scopes(app):
    request_id = await app["start"].execute(authorize(resource=MEALS, scope="meals:read meals:write"))
    await app["login"].execute(request_id, Subject("user-1"))
    code = (await app["consent"].execute(request_id, approved=True)).params["code"]
    body = await app["token"].execute(TokenCommand(code, REDIRECT, CLIENT_ID, VERIFIER, MEALS))
    claims = jwt.decode(body["access_token"], options={"verify_signature": False})
    assert (claims["aud"], claims["scope"]) == (MEALS, "meals:read meals:write")


async def tokens_for(app, resource=MCP) -> dict:
    scope = "read" if resource == MCP else "meals:read meals:write"
    request_id = await app["start"].execute(authorize(resource=resource, scope=scope))
    await app["login"].execute(request_id, Subject("user-1"))
    code = (await app["consent"].execute(request_id, approved=True)).params["code"]
    return await app["token"].execute(TokenCommand(code, REDIRECT, CLIENT_ID, VERIFIER, resource))


def claims_of(body: dict) -> dict:
    return jwt.decode(body["access_token"], options={"verify_signature": False})


@pytest.mark.anyio
async def test_refresh_token_issues_new_tokens_for_the_same_grant(app):
    first = await tokens_for(app, MEALS)
    second = await app["refresh"].execute(RefreshCommand(first["refresh_token"], CLIENT_ID, None))
    assert second["refresh_token"] != first["refresh_token"]  # ローテーション
    assert (claims_of(second)["aud"], claims_of(second)["scope"]) == (MEALS, "meals:read meals:write")
    third = await app["refresh"].execute(RefreshCommand(second["refresh_token"], CLIENT_ID, MEALS))
    assert claims_of(third)["sub"] == "user-1"


@pytest.mark.anyio
async def test_reused_refresh_token_revokes_the_whole_family(app):
    first = await tokens_for(app)
    second = await app["refresh"].execute(RefreshCommand(first["refresh_token"], CLIENT_ID, None))
    with pytest.raises(InvalidGrant):  # 古いものをもう一度使った（盗まれた可能性）
        await app["refresh"].execute(RefreshCommand(first["refresh_token"], CLIENT_ID, None))
    with pytest.raises(InvalidGrant):  # 系列ごと無効になったので、最新のものも使えない
        await app["refresh"].execute(RefreshCommand(second["refresh_token"], CLIENT_ID, None))


@pytest.mark.anyio
@pytest.mark.parametrize("command", [
    lambda rt: RefreshCommand(rt, "https://other.example/metadata.json", None),  # 別のクライアント
    lambda rt: RefreshCommand("unknown." + rt.partition(".")[2], CLIENT_ID, None),  # 知らない系列
    lambda rt: RefreshCommand("no-dot", CLIENT_ID, None),  # 形が正しくない
])
async def test_refresh_rejects_invalid_requests(app, command):
    first = await tokens_for(app)
    with pytest.raises(InvalidGrant):
        await app["refresh"].execute(command(first["refresh_token"]))


@pytest.mark.anyio
async def test_refresh_rejects_other_resource(app):
    first = await tokens_for(app)
    with pytest.raises(InvalidTarget):
        await app["refresh"].execute(RefreshCommand(first["refresh_token"], CLIENT_ID, MEALS))


@pytest.mark.anyio
@pytest.mark.parametrize("which", ["refresh_token", "access_token"])
async def test_revoking_either_token_ends_the_connection(app, which):
    tokens = await tokens_for(app)
    await app["revoke"].execute(tokens[which], CLIENT_ID)
    with pytest.raises(InvalidGrant):  # 系列ごと消えたので、リフレッシュできない
        await app["refresh"].execute(RefreshCommand(tokens["refresh_token"], CLIENT_ID, None))


@pytest.mark.anyio
@pytest.mark.parametrize("token", ["unknown.secret", "not-a-token", "a.b.c"])
async def test_revoking_unknown_token_does_nothing(app, token):
    tokens = await tokens_for(app)
    await app["revoke"].execute(token, CLIENT_ID)  # エラーにしない（RFC 7009）
    await app["refresh"].execute(RefreshCommand(tokens["refresh_token"], CLIENT_ID, None))


@pytest.mark.anyio
async def test_other_client_cannot_revoke(app):
    tokens = await tokens_for(app)
    await app["revoke"].execute(tokens["refresh_token"], "https://other.example/metadata.json")
    await app["refresh"].execute(RefreshCommand(tokens["refresh_token"], CLIENT_ID, None))  # まだ使える


@pytest.mark.anyio
async def test_access_token_carries_session_id(app):
    tokens = await tokens_for(app)
    family_id = tokens["refresh_token"].partition(".")[0]
    assert claims_of(tokens)["sid"] == family_id
    assert claims_of(tokens)["exp"] - claims_of(tokens)["iat"] == 300  # 5分


@pytest.mark.anyio
async def test_switch_account_restarts_login_on_the_same_request(app):
    request_id = await app["start"].execute(authorize())
    await app["login"].execute(request_id, Subject("wrong-user", "wrong@example.com"))
    await app["restart"].execute(request_id)
    view = await app["login"].execute(request_id, Subject("user-1", "u@example.com"))
    assert view.email == "u@example.com"
    code = (await app["consent"].execute(request_id, approved=True)).params["code"]
    body = await app["token"].execute(token_command(code))
    assert claims_of(body)["sub"] == "user-1"
