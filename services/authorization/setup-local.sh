#!/bin/sh
# CDK でデプロイしたユーザープールから services/authorization/.env を作り、テスト用ユーザーを用意する。
# クライアントシークレットとパスワードは画面に出さず、本人だけが読めるファイルに保存する。
set -eu
cd "$(dirname "$0")"
# AWS の認証情報は、環境変数（AWS_PROFILE など）で指定しておく
export AWS_REGION=ap-northeast-1

out() {
  aws cloudformation describe-stacks --stack-name CognitoStudy \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
POOL=$(out UserPoolId)
CID=$(out ClientId)
umask 077

{
  echo "COGNITO_ISSUER=$(out CognitoIssuer)"
  echo "COGNITO_CLIENT_ID=$CID"
  echo "COGNITO_CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client --user-pool-id "$POOL" --client-id "$CID" \
    --query UserPoolClient.ClientSecret --output text)"
} > .env
echo ".env を書きました"

USER=test1@example.com
if aws cognito-idp admin-get-user --user-pool-id "$POOL" --username "$USER" >/dev/null 2>&1; then
  echo "$USER はすでにあります"
  exit 0
fi
aws cognito-idp admin-create-user --user-pool-id "$POOL" --username "$USER" \
  --user-attributes Name=email,Value="$USER" Name=email_verified,Value=true \
  --message-action SUPPRESS >/dev/null
PW="$(openssl rand -base64 18 | tr -d '/+=')Aa1!"
printf '%s\n' "$PW" > .test1-password
aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username "$USER" --password "$PW" --permanent
echo "$USER を作りました（パスワードは services/authorization/.test1-password）"
