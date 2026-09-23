#!/usr/bin/env bash
set -euo pipefail

# このスクリプトがあるディレクトリに移動
cd "$(dirname "$0")"

# .env を読み込む
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  echo "ERROR: .env が見つかりません" >&2
  exit 1
fi

# 必須チェック
: "${JNKIE_SCRIPT_KEY:?JNKIE_SCRIPT_KEY が .env にありません}"
: "${CLIENT_TOKEN:?CLIENT_TOKEN が .env にありません}"

# venv があれば有効化
if [ -d "venv" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# 起動
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "Starting server on ${HOST}:${PORT} ..."
exec uvicorn server:app --host "${HOST}" --port "${PORT}"
