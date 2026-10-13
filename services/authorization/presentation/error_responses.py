"""ドメインのエラーを、OAuth のエラー応答に変える。"""

from urllib.parse import urlencode

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from domain.errors import OAuthError
from presentation.pages import render_error_page


def error_page(description: str) -> HTMLResponse:
    """redirect_uri へ返せないエラー（クライアントを確かめられない、など）はエラー画面にする。"""
    return HTMLResponse(render_error_page(description), status_code=400)


def redirect_with_error(redirect_uri: str, state: str | None, error: OAuthError, issuer: str) -> RedirectResponse:
    query = {"error": error.code, "iss": issuer}
    if state:
        query["state"] = state
    return RedirectResponse(f"{redirect_uri}?{urlencode(query)}", status_code=302)


def token_error(error: OAuthError) -> JSONResponse:
    """/token のエラー（RFC 6749 5.2）。"""
    return JSONResponse({"error": error.code, "error_description": error.description}, status_code=400)
