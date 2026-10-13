import pytest

from domain.errors import ClientRejected, InvalidRequest
from domain.values import ClientId, CodeChallenge, RedirectUri


@pytest.mark.parametrize("url", [
    "https://claude.ai/oauth/claude-code-client-metadata",
    "http://localhost:3005/client-metadata.json",
    "http://127.0.0.1:3005/client-metadata.json",
])
def test_client_id_accepts_https_and_local_http(url):
    assert ClientId(url).value == url


@pytest.mark.parametrize("url", [
    "http://evil.example/meta.json",  # localhost 以外の http
    "https://example.com",  # パスがない
    "https://example.com/",
    "https://user:pass@example.com/meta.json",
    "https://example.com/meta.json#x",
    "study-client",  # URL ではない
])
def test_client_id_rejects_invalid_urls(url):
    with pytest.raises(ClientRejected):
        ClientId(url)


def test_loopback_redirect_ignores_port():
    registered = RedirectUri("http://localhost/callback")
    assert RedirectUri("http://localhost:51234/callback").matches(registered)
    assert not RedirectUri("http://localhost:51234/evil").matches(registered)
    assert not RedirectUri("http://127.0.0.1:51234/callback").matches(registered)


def test_non_loopback_redirect_requires_exact_match():
    registered = RedirectUri("https://claude.ai/api/mcp/auth_callback")
    assert RedirectUri("https://claude.ai/api/mcp/auth_callback").matches(registered)
    assert not RedirectUri("https://claude.ai:8443/api/mcp/auth_callback").matches(registered)


def test_code_challenge_verifies_s256():
    # RFC 7636 付録 B の例
    challenge = CodeChallenge.from_request("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", "S256")
    assert challenge.verify("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
    assert not challenge.verify("wrong-verifier")


@pytest.mark.parametrize("challenge, method", [(None, "S256"), ("abc", "plain"), ("abc", None)])
def test_code_challenge_requires_s256(challenge, method):
    with pytest.raises(InvalidRequest):
        CodeChallenge.from_request(challenge, method)
