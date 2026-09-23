# server.py
import hashlib
import os
import time
import traceback
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

# ------------------------------------------------------------------
# 設定
# ------------------------------------------------------------------
API = (
    "https://api.jnkie.com/api/v1/luascripts/delivery/"
    "0c237fdefab6050afef9e14c974903d107432c6eee626c0dceb9561b6cd7d3cc"
    "?v=2&errors=text"
)

SCRIPT_KEY = os.environ["JNKIE_SCRIPT_KEY"]
CLIENT_TOKEN = os.environ["CLIENT_TOKEN"]

# HWID（環境変数で上書き可能。未設定ならデフォルト値を使う）
HWID = os.environ.get("JNKIE_HWID", "TEST-HWID-00000000")

# HWIDの送り方: "header" or "body" or "both"
HWID_MODE = os.environ.get("JNKIE_HWID_MODE", "header")

# ヘッダ名（環境によって違う可能性があるので変えられるように）
HWID_HEADER = os.environ.get("JNKIE_HWID_HEADER", "X-HWID")

# ------------------------------------------------------------------
# アプリ初期化
# ------------------------------------------------------------------
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_cache = {"url": None, "body": None, "hash": None, "ts": 0}
CACHE_TTL = 60


# ------------------------------------------------------------------
# デバッグ用：例外をそのまま返す（原因特定が終わったら外す）
# ------------------------------------------------------------------
@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    return PlainTextResponse(
        f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
        status_code=500,
    )


# ------------------------------------------------------------------
# JNKIE API へのリクエスト
# ------------------------------------------------------------------
def build_headers():
    headers = {"Content-Type": "text/plain"}
    if HWID_MODE in ("header", "both"):
        headers[HWID_HEADER] = HWID
    return headers


def build_body():
    if HWID_MODE in ("body", "both"):
        # 形式1: key + 改行 + hwid
        return f"{SCRIPT_KEY}\n{HWID}".encode()
        # 形式2: JSON
        # import json
        # return json.dumps({"key": SCRIPT_KEY, "hwid": HWID}).encode()
        # 形式3: key + "|" + hwid
        # return f"{SCRIPT_KEY}|{HWID}".encode()
    return SCRIPT_KEY.encode()


def fetch_from_api():
    headers = build_headers()
    body = build_body()

    r = requests.post(
        API,
        data=body,
        headers=headers,
        timeout=15,
        allow_redirects=False,
    )

    # ログ（RenderのLogsに出る）
    print(f"[JNKIE] POST status={r.status_code}")
    print(f"[JNKIE] headers sent={headers}")
    print(f"[JNKIE] body sent={body[:80]!r}")
    print(f"[JNKIE] response body={r.text[:300]!r}")

    # 200 + Body が CDN URL
    if r.status_code == 200 and r.text.startswith("https://cdn.jnkie.com/"):
        return r.text.strip()

    # 302/303 + Location
    if r.status_code in (302, 303):
        loc = r.headers.get("Location") or r.headers.get("location")
        if loc and loc.startswith("https://cdn.jnkie.com/"):
            return loc

    # 拒否系
    raise HTTPException(
        status_code=502,
        detail=f"api.jnkie.com returned {r.status_code}: {r.text[:300]}",
    )


def fetch_body(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text


# ------------------------------------------------------------------
# ルーティング
# ------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"client_token": CLIENT_TOKEN},
    )


@app.get("/url", response_class=PlainTextResponse)
def get_url(x_client_token: str = Header(default="")):
    if x_client_token != CLIENT_TOKEN:
        raise HTTPException(status_code=401, detail="bad token")

    now = time.time()
    if _cache["url"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["url"]

    url = fetch_from_api()
    _cache["url"] = url
    _cache["ts"] = now
    return url


@app.get("/body", response_class=PlainTextResponse)
def get_body(x_client_token: str = Header(default="")):
    if x_client_token != CLIENT_TOKEN:
        raise HTTPException(status_code=401, detail="bad token")

    now = time.time()
    if _cache["body"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["body"]

    url = fetch_from_api()
    body = fetch_body(url)
    _cache["url"] = url
    _cache["body"] = body
    _cache["hash"] = hashlib.sha256(body.encode()).hexdigest()
    _cache["ts"] = now
    return body


@app.get("/info")
def get_info(x_client_token: str = Header(default="")):
    if x_client_token != CLIENT_TOKEN:
        raise HTTPException(status_code=401, detail="bad token")

    url = fetch_from_api()
    body = fetch_body(url)
    return {
        "url": url,
        "length": len(body),
        "sha256": hashlib.sha256(body.encode()).hexdigest(),
    }


# デバッグ用：キャッシュをクリア
@app.get("/clear-cache")
def clear_cache(x_client_token: str = Header(default="")):
    if x_client_token != CLIENT_TOKEN:
        raise HTTPException(status_code=401, detail="bad token")
    _cache.update({"url": None, "body": None, "hash": None, "ts": 0})
    return {"ok": True}
