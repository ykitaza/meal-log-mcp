import httpx2


class AuthzApiSession:
    """認可APIに、連携の取り消しを頼む（RFC 7009 の /revoke）。

    本人のアクセストークンを送ると、認可APIはそのトークンを発行した連携（リフレッシュトークンの系列）ごと消す。
    """

    def __init__(self, trusted_issuer: str):
        self.trusted_issuer = trusted_issuer

    async def revoke(self, access_token: str, client_id: str) -> None:
        async with httpx2.AsyncClient(timeout=5) as client:
            res = await client.post(
                f"{self.trusted_issuer}/revoke", data={"token": access_token, "client_id": client_id})
            res.raise_for_status()

    def logout_url(self) -> str:
        """ブラウザで開くと、ログイン画面（Cognito）のセッションも消える。"""
        return f"{self.trusted_issuer}/logout"
