"""HTTP の入口。リクエストをユースケースの入力に変え、結果を HTTP の応答に変えるだけ。"""

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

from authlib.common.errors import AuthlibBaseError as LoginError
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from application.complete_login import CompleteLogin
from application.decide_consent import DecideConsent
from application.exchange_token import ExchangeToken, RefreshAccessToken, RefreshCommand, TokenCommand
from application.restart_login import RestartLogin
from application.revoke_token import RevokeToken
from application.server_metadata import authorization_server_metadata
from application.start_authorization import AuthorizeCommand, RedirectableError, StartAuthorization
from domain.errors import ClientRejected, InvalidRequest, OAuthError, UnsupportedGrantType
from domain.ports import AccessTokenIssuer
from domain.values import ResourceServer, Subject
from presentation.pages import render_consent_page, render_logged_out_page, render_privacy_page
from presentation.error_responses import error_page, redirect_with_error, token_error

# ブラウザのセッション（署名付き Cookie）に、進行中の認可リクエストの ID を入れておく
SESSION_KEY = "authorization_request_id"


class LoginGateway(Protocol):
    """本人確認（ログイン）の入口。ブラウザのリダイレクトを伴うので、HTTP の層で扱う。"""

    async def redirect_to_login(self, request: Request) -> Response: ...

    async def subject_from_callback(self, request: Request) -> Subject: ...

    async def logout_url(self, logout_uri: str) -> str:
        """ログイン画面のセッションを消し、logout_uri へ戻る URL。"""
        ...


@dataclass(frozen=True)
class Dependencies:
    issuer: str
    resource_servers: list[ResourceServer]
    start_authorization: StartAuthorization
    complete_login: CompleteLogin
    decide_consent: DecideConsent
    exchange_token: ExchangeToken
    refresh_access_token: RefreshAccessToken
    revoke_token: RevokeToken
    restart_login: RestartLogin
    token_issuer: AccessTokenIssuer
    login: LoginGateway


def create_router(deps: Dependencies) -> APIRouter:
    router = APIRouter()

    @router.get("/authorize")
    async def authorize(
        request: Request,
        client_id: str,
        redirect_uri: str,
        response_type: str | None = None,
        state: str | None = None,
        scope: str | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
        resource: str | None = None,
    ):
        cmd = AuthorizeCommand(
            client_id, redirect_uri, response_type, state, scope, code_challenge, code_challenge_method, resource)
        try:
            request_id = await deps.start_authorization.execute(cmd)
        except ClientRejected as e:
            return error_page(str(e))
        except RedirectableError as e:
            return redirect_with_error(e.redirect_uri, e.state, e.error, deps.issuer)
        request.session[SESSION_KEY] = request_id
        return await deps.login.redirect_to_login(request)

    @router.get("/cognito/callback")
    async def cognito_callback(request: Request):
        request_id = request.session.get(SESSION_KEY)
        if request_id is None:
            return error_page("認可リクエストが見つかりません（最初からやり直してください）")
        try:
            subject = await deps.login.subject_from_callback(request)
            view = await deps.complete_login.execute(request_id, subject)
        except (LoginError, OAuthError) as e:
            return error_page(f"ログインを確かめられません: {e}")
        # 別のサイトに埋め込んで「許可する」を押させる攻撃を防ぐ
        return HTMLResponse(render_consent_page(view), headers={"X-Frame-Options": "DENY"})

    @router.post("/consent")
    async def consent(request: Request, decision: str = Form()):
        # セッション Cookie は SameSite=Lax なので、別のサイトから送らせた POST には付かない
        request_id = request.session.pop(SESSION_KEY, None)
        if request_id is None:
            # 「許可する」の2回押しや再送信など。1回目で手続きは終わっていることが多い
            return error_page("この連携の手続きは、すでに終わっているか期限が切れています。"
                              "連携アプリの画面に戻って、つながっているかを確かめてください")
        try:
            res = await deps.decide_consent.execute(request_id, approved=(decision == "allow"))
        except OAuthError as e:
            return error_page(e.description)
        # POST への返事なので 303 にして、ブラウザに GET で移動させる
        return RedirectResponse(f"{res.redirect_uri}?{urlencode(res.params)}", status_code=303)

    @router.post("/token")
    async def token(
        grant_type: str = Form(),
        client_id: str = Form(),
        code: str | None = Form(None),
        redirect_uri: str | None = Form(None),
        code_verifier: str | None = Form(None),
        refresh_token: str | None = Form(None),
        resource: str | None = Form(None),
    ):
        try:
            if grant_type == "authorization_code":
                if not (code and redirect_uri and code_verifier):
                    raise InvalidRequest("code・redirect_uri・code_verifier が必要です")
                body = await deps.exchange_token.execute(
                    TokenCommand(code, redirect_uri, client_id, code_verifier, resource))
            elif grant_type == "refresh_token":
                if not refresh_token:
                    raise InvalidRequest("refresh_token が必要です")
                body = await deps.refresh_access_token.execute(RefreshCommand(refresh_token, client_id, resource))
            else:
                raise UnsupportedGrantType("authorization_code と refresh_token だけに対応しています")
        except ClientRejected as e:
            return token_error(OAuthError(str(e)))
        except OAuthError as e:
            return token_error(e)
        return JSONResponse(body, headers={"Cache-Control": "no-store"})

    @router.post("/revoke")
    async def revoke(token: str = Form(), client_id: str = Form()):
        # RFC 7009：知らないトークンでも 200 を返す（トークンが有効かどうかを外から探らせないため）
        await deps.revoke_token.execute(token, client_id)
        return Response(status_code=200, headers={"Cache-Control": "no-store"})

    @router.get("/switch-account")
    async def switch_account(request: Request):
        """同意画面の「別のアカウントで入り直す」。Cognito のセッションを消してから、ログイン画面に戻る。"""
        request_id = request.session.get(SESSION_KEY)
        if request_id is None:
            return error_page("認可リクエストが見つかりません（最初からやり直してください）")
        try:
            await deps.restart_login.execute(request_id)
        except OAuthError as e:
            return error_page(e.description)
        return RedirectResponse(await deps.login.logout_url(f"{deps.issuer}/relogin"))

    @router.get("/relogin")
    async def relogin(request: Request):
        """Cognito のセッションを消したあとに戻ってくる。同じ認可リクエストのまま、ログイン画面へ。"""
        if request.session.get(SESSION_KEY) is None:
            return error_page("認可リクエストが見つかりません（最初からやり直してください）")
        return await deps.login.redirect_to_login(request)

    @router.get("/logout")
    async def logout(request: Request):
        """ログアウト：このブラウザのセッションと、Cognito のログイン画面のセッションを消す。"""
        request.session.clear()
        return RedirectResponse(await deps.login.logout_url(f"{deps.issuer}/logged-out"))

    @router.get("/logged-out", response_class=HTMLResponse)
    def logged_out():
        return render_logged_out_page()

    @router.get("/.well-known/oauth-authorization-server")
    def metadata():
        return authorization_server_metadata(deps.issuer, deps.resource_servers)

    @router.get("/privacy", response_class=HTMLResponse)
    def privacy():
        return render_privacy_page()

    @router.get("/.well-known/jwks.json")
    def jwks():
        return deps.token_issuer.jwks()

    return router
