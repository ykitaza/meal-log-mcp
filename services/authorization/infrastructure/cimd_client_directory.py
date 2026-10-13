import httpx

from domain.client import Client
from domain.errors import ClientRejected
from domain.values import ClientId, RedirectUri

CIMD_MAX_BYTES = 5 * 1024


class CimdClientDirectory:
    """ClientDirectory の実装。CIMD：client_id の URL から、クライアントの情報を書いた文書を取りに行く。"""

    def __init__(self, http_get=None):
        self.http_get = http_get or self._get

    async def find(self, client_id: ClientId) -> Client:
        # 本番では、社内ネットワークの宛先を取りに行かないように制限する（SSRF の対策）
        try:
            res = await self.http_get(client_id.value)
        except httpx.HTTPError:
            raise ClientRejected("クライアントのメタデータを取得できません")
        if res.status_code != 200 or len(res.content) > CIMD_MAX_BYTES:
            raise ClientRejected("クライアントのメタデータを取得できません")
        try:
            doc = res.json()
        except ValueError:
            raise ClientRejected("クライアントのメタデータが JSON ではありません")

        # 文書の中の client_id が、取りに行った URL と同じか（他人の文書を使い回していないか）
        if doc.get("client_id") != client_id.value:
            raise ClientRejected("メタデータの client_id が URL と一致しません")
        # シークレットを持たないクライアント（PKCE で確かめる）だけを受け付ける。
        # ChatGPT は token_endpoint_auth_method に private_key_jwt を書き、対応できる方式の一覧
        # （token_endpoint_auth_methods_supported、CIMD の標準の項目ではない）に none も書いている。
        # 認可APIのメタデータは none だけを公開しているので、そちらで来る
        method = doc.get("token_endpoint_auth_method", "none")
        if "none" not in [method, *doc.get("token_endpoint_auth_methods_supported", [])]:
            raise ClientRejected("token_endpoint_auth_method は none だけに対応しています")
        if not isinstance(doc.get("redirect_uris"), list):
            raise ClientRejected("メタデータに redirect_uris がありません")
        return Client(
            id=client_id,
            name=doc.get("client_name") or client_id.value,
            redirect_uris=tuple(RedirectUri(uri) for uri in doc["redirect_uris"]),
        )

    @staticmethod
    async def _get(url: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            return await client.get(url)
