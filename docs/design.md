# 全体の設計

食事記録そのもの（ドメイン、ツール、目標の計算）の設計は [meals-design.md](meals-design.md)、ログインからツールの呼び出しまでの流れは [シーケンス図](sequence.md) にあります。

## なぜ Cognito の前に自作の認可API を置くのか

MCP の仕様は、クライアント（Claude・ChatGPT）を事前登録せずに使える OAuth を求めています。Cognito だけを認可サーバーにすると、次の点が足りません。

- client_id に URL を使い、そこからクライアント情報を取る方式（CIMD）
- トークンの宛先を MCP サーバーに限る `resource` パラメータ（RFC 8707）
- 認可サーバーの情報を返す `/.well-known/oauth-authorization-server`（RFC 8414）

そのため、本人確認（ログイン画面）だけを Cognito に任せ、どのクライアントに何を許すかは自作の認可API が決めます。

## 境界づけられたコンテキスト

```
本人確認（Cognito）──IDトークン──► 認可（services/authorization/）──アクセストークン──► 食事記録（services/meals/）
```

| コンテキスト | 扱う問い | 担当 |
|---|---|---|
| 本人確認 | この人は誰か | 外部のシステム（Cognito） |
| 認可 | どのクライアントに、誰の、何を許したか | `services/authorization/` |
| 食事記録 | この人は何を食べ、目標とどれだけ違うか | `services/meals/`（MCP サーバー） |

- 本人確認 → 認可：`services/authorization/infrastructure/cognito_login.py`（腐敗防止層、Authlib）が IDトークンを `Subject` に変えます
- 認可 → 食事記録：受け渡すのはアクセストークン（JWT）だけです。食事記録は、認可APIの iss と JWKS を手で設定して信じます
- scope はリソースサーバーごとに持ちます（食事記録は `meals:read`・`meals:write`）
- MCP は食事記録を外に出す通信の形式なので、`services/meals/presentation/` に置きます

## フォルダと層

各コンテキストは DDD の層に分けています。依存の向きは `presentation` → `application` → `domain` ← `infrastructure`、組み立て（DI）は `main.py` で行います。

| フォルダ | 中身 |
|---|---|
| `services/authorization/` | 認可API。集約は認可リクエスト（本人確認待ち → 同意待ち → 許可／拒否）と認可コード、リフレッシュトークンの系列。CIMD、PKCE、RFC 8707、RFC 9207、同意画面、プライバシーポリシー（`/privacy`） |
| `services/meals/` | MCP サーバー。食事の記録・修正・いつもの・目標・今日の残り・週のふり返り・体重と目標までの進み具合・ログアウト（ツール18個） |
| `cdk/` | AWS の構成（CDK）。Cognito（新規登録は不可）、Lambda 2つ（入口は API Gateway の HTTP API、流量の制限付き）、DynamoDB 2つ、SSM パラメータ |
| `tools/inspector/` | MCP Inspector 用の CIMD の文書（PC で食事記録を試すとき） |
| `docs/` | 設計書と図 |

## 外から届く道を絞る

本人だけで使うので、次のように絞っています。

- 入口は API Gateway の HTTP API だけにしています（Lambda の関数 URL は使いません）
- 流量の制限は 1秒1回・瞬間5回です。超えた分は 429 で断るので、叩かれ続けても月の費用に上限がかかります
- Cognito のログイン画面からの新規登録はできません。ユーザーは管理者の操作（`setup-local.sh`）でだけ作ります
