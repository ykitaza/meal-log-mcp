"""診断用のログ。JSON-RPC のメソッドと、ツールの名前・リソースの URI だけを記録する（引数の値は記録しない）。"""

import json
import logging

logger = logging.getLogger("meals.requests")


class JsonRpcLogMiddleware:
    """ASGI のミドルウェア。本文を読んでログに出し、アプリにはそのまま渡す。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        chunks, more = [], True
        while more:
            message = await receive()
            chunks.append(message.get("body", b""))
            more = message.get("more_body", False)
        body = b"".join(chunks)
        _log(body)

        async def replay():
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


def _log(body: bytes) -> None:
    try:
        messages = json.loads(body)
    except ValueError:
        return
    for msg in messages if isinstance(messages, list) else [messages]:
        if not isinstance(msg, dict) or "method" not in msg:
            continue
        params = msg.get("params") or {}
        detail = ""
        if msg["method"] in ("initialize", "server/discover"):
            # MCP Apps に対応すると名乗っているか（拡張の宣言）を見るため、capabilities の項目名だけを出す
            capabilities = params.get("capabilities") or (params.get("_meta") or {}).get("capabilities") or {}
            detail = (
                f"client={(params.get('clientInfo') or {}).get('name')} version={params.get('protocolVersion')} "
                f"params={sorted(params)} capabilities={_keys(capabilities)}"
            )
        elif msg["method"] == "tools/call":
            detail = f"tool={params.get('name')}"
        elif msg["method"] == "resources/read":
            detail = f"uri={params.get('uri')}"
        logger.info("jsonrpc %s %s", msg["method"], detail)


def _keys(value: dict, depth: int = 2) -> dict | list:
    """値は出さず、入れ子の項目名だけを返す。"""
    if depth == 0 or not isinstance(value, dict):
        return []
    return {k: _keys(v, depth - 1) if isinstance(v, dict) else [] for k, v in value.items()}
