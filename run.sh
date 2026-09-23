#!/usr/bin/env bash
set -e

# .env があれば読み込む
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# 必須チェック
: "${JNKIE_SCRIPT_KEY:?JNKIE_SCRIPT_KEY is not set}"
: "${CLIENT_TOKEN:?CLIENT_TOKEN is not set}"

uvicorn server:app --host 0.0.0.0 --port 8000
