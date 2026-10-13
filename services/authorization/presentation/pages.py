"""ブラウザに出す画面（同意画面、プライバシーポリシー、エラー画面）。外部の CSS や JS は読み込まない。"""

import html

from application.complete_login import ConsentView

# 同意画面に表示する scope の説明
SCOPE_DESCRIPTIONS = {
    "meals:read": "食事記録と目標の読み取り",
    "meals:write": "食事記録と目標の追加・修正・削除",
}

# 余白・色・文字の大きさは、ここの変数だけを使う（余白は 8px 刻み）
STYLE = """
:root {
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-6: 24px; --space-8: 32px; --space-12: 48px;
  --text-sm: 14px; --text-base: 16px; --text-lg: 20px; --text-xl: 28px;
  --radius: 8px;
  --bg: #f6f6f4; --surface: #ffffff; --border: #dcdcd7;
  --text: #1c1c1a; --muted: #5c5c57; --accent: #1f6f5c; --accent-text: #ffffff;
  --font: "Hiragino Sans", "Noto Sans JP", system-ui, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161615; --surface: #20201e; --border: #3a3a37;
    --text: #ededea; --muted: #a8a8a2; --accent: #5cb89f; --accent-text: #0e1a17;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: var(--text-base)/1.6 var(--font);
}
main { max-width: 40em; margin-inline: auto; padding: var(--space-8) var(--space-4) var(--space-12); }
.service { margin: 0 0 var(--space-6); font-size: var(--text-sm); color: var(--muted); }
h1 { margin: 0 0 var(--space-6); font-size: var(--text-xl); line-height: 1.25; }
h2 { margin: var(--space-8) 0 var(--space-2); font-size: var(--text-lg); line-height: 1.25; }
p, ul { margin: 0 0 var(--space-4); }
ul { padding-left: var(--space-6); }
li + li { margin-top: var(--space-1); }
a { color: var(--accent); }
.panel {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: var(--space-6); margin-bottom: var(--space-6);
}
.panel > :last-child { margin-bottom: 0; }
.client-name { margin: 0; font-size: var(--text-lg); font-weight: 700; }
.client-host { margin: 0 0 var(--space-4); font: var(--text-sm)/1.6 var(--mono); color: var(--muted); }
.note { font-size: var(--text-sm); color: var(--muted); }
.actions { display: flex; flex-direction: column; gap: var(--space-3); }
button {
  min-height: 48px; padding: 0 var(--space-6); border-radius: var(--radius);
  font: 700 var(--text-base)/1 var(--font); cursor: pointer;
}
.allow { background: var(--accent); color: var(--accent-text); border: 1px solid var(--accent); }
.deny { background: transparent; color: var(--text); border: 1px solid var(--border); }
button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
@media (min-width: 640px) {
  main { padding-top: var(--space-12); }
  .actions { flex-direction: row-reverse; justify-content: flex-start; }
}
"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<main>
<p class="service">食事管理 アカウント連携</p>
{body}
</main>
</body>
</html>"""


def render_consent_page(view: ConsentView) -> str:
    # client_name はクライアントが自由に書ける値なので、必ずエスケープする。偽の名前に備えてドメインも並べて出す
    scopes = "".join(f"<li>{html.escape(SCOPE_DESCRIPTIONS.get(s, s))}</li>" for s in view.scopes)
    meals = any(s.startswith("meals:") for s in view.scopes)
    photo_note = "食事の写真はこのサービスに送られず、保存もしません。" if meals else ""
    return _page("連携の確認", f"""<h1>連携の確認</h1>
<section class="panel">
<p class="client-name">{html.escape(view.client_name)}</p>
<p class="client-host">{html.escape(view.client_host)}</p>
<p>このアプリが、{html.escape(view.email)} さんの次の操作を求めています。
<a href="/switch-account">別のアカウントで入り直す</a></p>
<ul>{scopes}</ul>
</section>
<p class="note">心当たりのないアプリなら、許可しないでください。{photo_note}詳しくは<a href="/privacy" target="_blank">プライバシーポリシー</a>をご覧ください。</p>
<form method="post" action="/consent" class="actions"
  onsubmit="for (const b of this.querySelectorAll('button')) setTimeout(() => b.disabled = true)">
<button name="decision" value="allow" class="allow">許可する</button>
<button name="decision" value="deny" class="deny">許可しない</button>
</form>""")


def render_privacy_page() -> str:    return _page("プライバシーポリシー", """<h1>プライバシーポリシー</h1>
<p class="note">制定日：2026年10月12日</p>
<p>食事管理（以下「このサービス」）は、OAuth と MCP の仕組みを学ぶために個人が作った勉強用のアプリです。Claude や ChatGPT などのアプリ（以下「連携アプリ」）から、食事記録を扱えるようにします。</p>

<h2>集める情報</h2>
<ul>
<li>ログインに使うメールアドレスと、利用者を見分ける ID（Amazon Cognito が発行するもの）</li>
<li>連携アプリの名前と URL、許可した操作の種類</li>
<li>食事記録：食べた日・区分・時刻、品目・量・カロリーと栄養素、食事の説明文</li>
<li>目標：方針（増量・減量・維持）、体重、目標体重、1日の目標、食事の傾向、筋トレの日かどうか</li>
<li>体重の記録：日付と体重</li>
<li>目標の計算に使う情報：性別、年齢、身長、普段の活動量、筋トレ1回の時間（計算にだけ使い、保存しません）</li>
</ul>

<h2>写真の扱い</h2>
<p>食事の写真は、このサービスには送られず、保存もしません。写真の解析は連携アプリが行い、このサービスには解析の結果（品目・量・栄養素・説明文）だけが届きます。連携アプリでの写真の扱いは、それぞれのアプリのプライバシーポリシーに従います。</p>

<h2>使い道</h2>
<p>集めた情報は、本人に記録と集計（1日の合計、目標との差、週のふり返り）を返すためだけに使います。広告には使わず、第三者に提供しません。</p>

<h2>保存する場所と期間</h2>
<ul>
<li>保存する場所：Amazon Web Services の東京リージョン</li>
<li>食事記録・目標・体重の記録：本人が消すまで</li>
<li>連携の途中の情報：最大10分（認可コードは60秒）</li>
<li>連携アプリに渡すアクセストークンの有効期間：5分</li>
<li>連携アプリに渡すリフレッシュトークン（ログインし直さずに連携を続けるためのもの）の有効期間：最後に使ってから30日</li>
</ul>

<h2>記録の削除と連携の解除</h2>
<p>食事記録は、連携アプリから1件ずつ消せます。すべての記録をまとめて消す方法は、今は用意していません。連携をやめるときは、連携アプリでログアウトを頼むか、連携アプリの設定からこのサービスを外してください。</p>

<h2>改定</h2>
<p>このポリシーを変えるときは、このページで知らせます。</p>""")


def render_logged_out_page() -> str:
    return _page("ログアウトしました", """<h1>ログアウトしました</h1>
<section class="panel"><p>このブラウザのログインを終了しました。
連携アプリ（Claude・ChatGPT）でもう一度使うと、ログイン画面が表示されます。このページは閉じて構いません。</p></section>""")


def render_error_page(description: str) -> str:
    return _page("エラー", f"""<h1>連携を続けられません</h1>
<section class="panel"><p>{html.escape(description)}</p></section>""")
