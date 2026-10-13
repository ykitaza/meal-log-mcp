from domain.values import ResourceServer


def authorization_server_metadata(issuer: str, resource_servers: list[ResourceServer]) -> dict:
    """RFC 8414：OAuth クライアントが認可APIの入口と、対応している方式を知るための文書。"""
    scopes = [scope for server in resource_servers for scope in server.scopes.values]
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/authorize",
        "token_endpoint": f"{issuer}/token",
        "jwks_uri": f"{issuer}/.well-known/jwks.json",
        "revocation_endpoint": f"{issuer}/revoke",  # RFC 7009
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],  # シークレットなし（PKCE で確かめる）
        "scopes_supported": scopes,  # すべてのリソースサーバーの scope。どれが使えるかはリソースサーバーごとに違う
        "authorization_response_iss_parameter_supported": True,  # RFC 9207
        "client_id_metadata_document_supported": True,  # CIMD
    }
