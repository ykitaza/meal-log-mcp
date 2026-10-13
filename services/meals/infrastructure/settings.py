"""設定の読み込み。PC では既定値、Lambda では環境変数と SSM パラメータストアから読む。"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    trusted_issuer: str  # 信じる認可API（アクセストークンの iss）。信頼関係は手で設定する
    resource_url: str  # このMCPサーバーの名前（RFC 8707 の resource、アクセストークンの aud）
    table_name: str | None  # None ならメモリーに置く（PC 用。止めると消える）
    on_lambda: bool


def load_settings() -> Settings:
    trusted_issuer = os.environ.get("AUTHZ_ISSUER", "http://localhost:3000").rstrip("/")
    table_name = os.environ.get("MEALS_TABLE")
    if "AWS_LAMBDA_FUNCTION_NAME" not in os.environ:
        return Settings(trusted_issuer, "http://localhost:8001/mcp", table_name, on_lambda=False)

    import boto3  # Lambda の実行環境に入っている

    # 自分の関数 URL は作成後に決まるので、CDK が SSM に書いたものを読む
    own_url = boto3.client("ssm").get_parameter(Name=os.environ["MCP_URL_PARAM"])["Parameter"]["Value"]
    return Settings(trusted_issuer, own_url.rstrip("/") + "/mcp", table_name, on_lambda=True)
