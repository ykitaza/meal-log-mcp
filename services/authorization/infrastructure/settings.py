"""設定の読み込み。PC では .env とファイル、Lambda では環境変数と SSM パラメータストアから読む。"""

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    issuer: str  # 認可API自身の URL（アクセストークンの iss）
    meals_resource: str  # 食事記録の MCP サーバー（RFC 8707 の resource）
    cognito_issuer: str
    cognito_client_id: str
    cognito_client_secret: str
    signing_key_pem: str  # アクセストークンに署名する秘密鍵
    session_secret: str  # ブラウザのセッション Cookie に署名する鍵
    state_table: str | None  # DynamoDB のテーブル名。None ならメモリーに置く
    on_lambda: bool


def new_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


def load_local_settings() -> Settings:
    load_dotenv(APP_DIR / ".env")

    def secret_file(name: str, create) -> str:
        # 初回に作ってファイルに保存し、再起動しても同じ値を使う
        path = APP_DIR / name
        if not path.exists():
            path.write_text(create())
            path.chmod(0o600)
        return path.read_text()

    return Settings(
        issuer="http://localhost:3000",
        meals_resource="http://localhost:8001/mcp",
        cognito_issuer=os.environ["COGNITO_ISSUER"],
        cognito_client_id=os.environ["COGNITO_CLIENT_ID"],
        cognito_client_secret=os.environ["COGNITO_CLIENT_SECRET"],
        signing_key_pem=secret_file(".authz-private-key.pem", new_private_key_pem),
        session_secret=secret_file(".session-secret", lambda: secrets.token_urlsafe(32)),
        state_table=None,
        on_lambda=False,
    )


def load_lambda_settings() -> Settings:
    import boto3  # Lambda の実行環境に入っている

    ssm = boto3.client("ssm")

    def param(name: str) -> str:
        return ssm.get_parameter(Name=name)["Parameter"]["Value"]

    def secret_param(name: str, create) -> str:
        # Lambda ではファイルを残せないので、SSM に暗号化して置く。なければ作る
        try:
            return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
        except ssm.exceptions.ParameterNotFound:
            try:
                ssm.put_parameter(Name=name, Value=create(), Type="SecureString", Overwrite=False)
            except ssm.exceptions.ParameterAlreadyExists:
                pass  # 別の実行環境が同時に作った。そちらを使う
            return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]

    env = os.environ
    # 自分の関数 URL は作成後に決まるので、CDK が SSM に書いたものを読む。
    # Cognito のクライアント ID も同じ理由で SSM から、シークレットは環境変数に置かずに Cognito から読む
    cognito_client_id = param(env["COGNITO_CLIENT_ID_PARAM"])
    cognito_client_secret = boto3.client("cognito-idp").describe_user_pool_client(
        UserPoolId=env["COGNITO_USER_POOL_ID"], ClientId=cognito_client_id)["UserPoolClient"]["ClientSecret"]
    return Settings(
        issuer=param(env["AUTHZ_URL_PARAM"]).rstrip("/"),
        meals_resource=param(env["MEALS_URL_PARAM"]).rstrip("/") + "/mcp",
        cognito_issuer=env["COGNITO_ISSUER"],
        cognito_client_id=cognito_client_id,
        cognito_client_secret=cognito_client_secret,
        signing_key_pem=secret_param(env["SIGNING_KEY_PARAM"], new_private_key_pem),
        session_secret=secret_param(env["SESSION_SECRET_PARAM"], lambda: secrets.token_urlsafe(32)),
        state_table=env["STATE_TABLE"],
        on_lambda=True,
    )


def load_settings() -> Settings:
    return load_lambda_settings() if "AWS_LAMBDA_FUNCTION_NAME" in os.environ else load_local_settings()
