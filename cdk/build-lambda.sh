#!/bin/sh
# authorization・meals を、Lambda（arm64、Python 3.12）に載せる形にまとめて cdk/build/ に置く。
# cdk deploy の前に実行する。Docker は使わず、uv で Lambda 用のパッケージを入れる。
set -eu
cd "$(dirname "$0")"

for app in authorization meals; do
  out="build/$app"
  rm -rf "$out"
  mkdir -p "$out"
  (cd "../services/$app" && uv export --frozen --no-dev --no-hashes --quiet -o "../../cdk/$out/requirements.txt")
  uv pip install --quiet -r "$out/requirements.txt" --target "$out" \
    --python-platform aarch64-manylinux2014 --python-version 3.12 --only-binary :all:
  cp ../services/$app/*.py "$out/"
  # DDD の層（domain/ application/ infrastructure/ presentation/ など）もコピーする。テストは載せない
  for pkg in ../services/$app/*/__init__.py; do
    [ -e "$pkg" ] || continue  # サブパッケージがない場合
    dir=$(dirname "$pkg")
    [ "$(basename "$dir")" = tests ] || cp -R "$dir" "$out/"
  done
  # Lambda Web Adapter がこのスクリプトでアプリを起動し、HTTP のリクエストを渡す
  cat > "$out/run.sh" <<'EOF'
#!/bin/sh
exec python -m uvicorn main:app --host 0.0.0.0 --port 8080
EOF
  chmod +x "$out/run.sh"
  echo "$out を作りました"
done
