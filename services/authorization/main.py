"""組み立て（DI）。設定を読み、PC か Lambda かで差し込むアダプターを選んで、アプリを作る。

依存の向き：presentation → application → domain ← infrastructure。すべての層を知っているのはこのファイルだけ。
"""

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from application.complete_login import CompleteLogin
from application.decide_consent import DecideConsent
from application.exchange_token import ExchangeToken, RefreshAccessToken
from application.restart_login import RestartLogin
from application.revoke_token import RevokeToken
from application.start_authorization import StartAuthorization
from domain.values import ResourceIndicator, ResourceServer, Scope
from infrastructure.cimd_client_directory import CimdClientDirectory
from infrastructure.cognito_login import CognitoLogin
from infrastructure.jwt_access_token_issuer import JwtAccessTokenIssuer
from infrastructure.settings import load_settings
from presentation.routes import Dependencies, create_router


def create_app() -> FastAPI:
    settings = load_settings()

    if settings.state_table:
        from infrastructure.dynamodb_repositories import (
            DynamoDBAuthorizationCodeRepository,
            DynamoDBAuthorizationRequestRepository,
            DynamoDBRefreshTokenFamilyRepository,
        )

        requests = DynamoDBAuthorizationRequestRepository(settings.state_table)
        codes = DynamoDBAuthorizationCodeRepository(settings.state_table)
        families = DynamoDBRefreshTokenFamilyRepository(settings.state_table)
    else:
        from infrastructure.memory_repositories import (
            MemoryAuthorizationCodeRepository,
            MemoryAuthorizationRequestRepository,
            MemoryRefreshTokenFamilyRepository,
        )

        requests = MemoryAuthorizationRequestRepository()
        codes = MemoryAuthorizationCodeRepository()
        families = MemoryRefreshTokenFamilyRepository()

    token_issuer = JwtAccessTokenIssuer(settings.signing_key_pem, settings.issuer)
    # 知っているリソースサーバーと、そこで使える scope。信頼関係は手で設定する
    resource_servers = [
        ResourceServer(ResourceIndicator(settings.meals_resource), Scope(("meals:read", "meals:write"))),
    ]
    deps = Dependencies(
        issuer=settings.issuer,
        resource_servers=resource_servers,
        start_authorization=StartAuthorization(
            clients=CimdClientDirectory(),
            requests=requests,
            allowed_resources=resource_servers,
        ),
        complete_login=CompleteLogin(requests),
        decide_consent=DecideConsent(requests, codes, settings.issuer),
        exchange_token=ExchangeToken(codes, families, token_issuer),
        refresh_access_token=RefreshAccessToken(families, token_issuer),
        revoke_token=RevokeToken(families, token_issuer),
        restart_login=RestartLogin(requests),
        token_issuer=token_issuer,
        login=CognitoLogin(
            issuer=settings.cognito_issuer,
            client_id=settings.cognito_client_id,
            client_secret=settings.cognito_client_secret,
            redirect_uri=f"{settings.issuer}/cognito/callback",
        ),
    )

    app = FastAPI()
    app.include_router(create_router(deps))
    # ブラウザのセッション（署名付き Cookie）。Authlib の state・nonce と、進行中の認可リクエストの ID を入れる
    app.add_middleware(
        SessionMiddleware, secret_key=settings.session_secret, same_site="lax", https_only=settings.on_lambda)
    return app


app = create_app()
