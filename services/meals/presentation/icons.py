"""コネクタのアイコン。接続時に伝える（serverInfo.icons）ほか、ファビコンとしても返す。

Claude がカスタムコネクタのアイコンをどこから取るかは公開されていないので、両方を用意する。
"""

import base64
from pathlib import Path

from mcp_types import Icon

STATIC = Path(__file__).parent / "static"
FILES = {  # パス → （ファイル名, Content-Type）
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
    "/favicon.svg": ("icon.svg", "image/svg+xml"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
}
INDEX_HTML = b"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>\xe9\xa3\x9f\xe4\xba\x8b\xe8\xa8\x98\xe9\x8c\xb2</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="apple-touch-icon" href="/apple-touch-icon.png"></head><body></body></html>"""


def server_icons(origin: str) -> list[Icon]:
    """serverInfo.icons：SVG はデータ URI で（取りに行かなくて済む）、PNG は URL で渡す。"""
    svg = base64.b64encode((STATIC / "icon.svg").read_bytes()).decode()
    return [
        Icon(src=f"data:image/svg+xml;base64,{svg}", mime_type="image/svg+xml", sizes=["any"]),
        Icon(src=f"{origin}/apple-touch-icon.png", mime_type="image/png", sizes=["180x180"]),
    ]


class IconMiddleware:
    """ASGI のミドルウェア。GET でアイコンのパスと / が来たら返し、ほかはアプリに渡す（認証は不要）。"""

    def __init__(self, app):
        self.app = app
        self.files = {path: ((STATIC / name).read_bytes(), mime) for path, (name, mime) in FILES.items()}
        self.files["/"] = (INDEX_HTML, "text/html; charset=utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in ("GET", "HEAD") and scope["path"] in self.files:
            body, mime = self.files[scope["path"]]
            await send({"type": "http.response.start", "status": 200, "headers": [
                (b"content-type", mime.encode()), (b"cache-control", b"public, max-age=86400")]})
            await send({"type": "http.response.body", "body": b"" if scope["method"] == "HEAD" else body})
            return
        await self.app(scope, receive, send)
