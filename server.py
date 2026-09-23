# server.py
import hashlib
import os
import time
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import requests

API = ("https://api.jnkie.com/api/v1/luascripts/delivery/"
       "0c237fdefab6050afef9e14c974903d107432c6eee626c0dceb9561b6cd7d3cc"
       "?v=2&errors=text")

SCRIPT_KEY = os.environ["JNKIE_SCRIPT_KEY"]
CLIENT_TOKEN = os.environ["CLIENT_TOKEN"]

app = FastAPI()
templates = Jinja2Templates(directory="templates")

_cache = {"url": None, "body": None, "hash": None, "ts": 0}
CACHE_TTL = 60


def fetch_from_api():
    r = requests.post(
        API,
        data=SCRIPT_KEY.encode(),
        headers={"Content-Type": "text/plain"},
        timeout=15,
        allow_redirects=False,
    )
    if r.status_code == 200 and r.text.startswith("https://cdn.jnkie.com/"):
        return r.text.strip()
    if r.status_code in (302, 303):
        loc = r.headers.get("Location") or r.headers.get("location")
        if loc and loc.startswith("https://cdn.jnkie.com/"):
            return loc
    raise HTTPException(
        status_code=502,
        detail=f"api.jnkie.com returned {r.status_code}: {r.text[:200]}",
    )


def fetch_body(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text


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
