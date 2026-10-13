import httpx
import pytest

from domain.errors import ClientRejected
from domain.values import ClientId, RedirectUri
from infrastructure.cimd_client_directory import CimdClientDirectory

CLIENT_ID = "https://client.example/metadata.json"
DOC = {"client_id": CLIENT_ID, "client_name": "Example", "redirect_uris": ["https://client.example/callback"]}


def directory(status=200, json=None, error=None):
    async def http_get(url):
        if error:
            raise error
        return httpx.Response(status, json=DOC if json is None else json)

    return CimdClientDirectory(http_get=http_get)


@pytest.mark.anyio
async def test_reads_client_from_metadata_document():
    client = await directory().find(ClientId(CLIENT_ID))
    assert (client.name, client.redirect_uris) == ("Example", (RedirectUri("https://client.example/callback"),))


@pytest.mark.anyio
async def test_accepts_client_that_also_supports_none():
    # ChatGPT の文書の形
    doc = {**DOC, "token_endpoint_auth_method": "private_key_jwt",
           "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"]}
    assert (await directory(json=doc).find(ClientId(CLIENT_ID))).name == "Example"


@pytest.mark.anyio
@pytest.mark.parametrize("kwargs", [
    {"status": 404},
    {"error": httpx.ConnectError("down")},
    {"json": {**DOC, "client_id": "https://other.example/metadata.json"}},  # 他人の文書の使い回し
    {"json": {**DOC, "token_endpoint_auth_method": "client_secret_basic"}},
    {"json": {"client_id": CLIENT_ID}},  # redirect_uris がない
])
async def test_rejects_unusable_documents(kwargs):
    with pytest.raises(ClientRejected):
        await directory(**kwargs).find(ClientId(CLIENT_ID))
