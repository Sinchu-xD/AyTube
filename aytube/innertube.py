"""
innertube.py - YouTube internal API client.

Uses YouTube's private innertube API (youtubei/v1/player) to fetch
streaming data directly. URLs come pre-signed without requiring
obfuscated signature deciphering.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
import http.cookiejar
from typing import Any

# Default innertube client config (ANDROID_VR provides direct URLs without cipher/poToken)
_DEFAULT_CLIENT = {
    "clientName": "ANDROID_VR",
    "clientVersion": "1.56.21",
    "deviceModel": "Quest 3",
    "hl": "en",
    "gl": "US",
}

# Innertube API endpoint
_INNERTUBE_URL = "https://www.youtube.com/youtubei/v1/player"


def _find_cookies(cookies_file: str | None = None) -> str | None:
    """Find cookies_file from parameter or default search locations."""
    if cookies_file and os.path.isfile(cookies_file):
        return cookies_file
    candidates = [
        os.path.join(os.getcwd(), "cookies_file"),
        os.path.join(os.path.dirname(__file__), "..", "cookies_file"),
        os.path.expanduser("~/.config/aytube/cookies_file"),
    ]
    for c in candidates:
        norm = os.path.normpath(c)
        if os.path.isfile(norm):
            return norm
    return None


def _build_headers(cookies_file: str | None = None) -> dict[str, str]:
    """Build headers for innertube API requests."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://www.youtube.com",
        "Referer": "https://www.youtube.com/",
    }

    cf = _find_cookies(cookies_file)
    if cf:
        try:
            cj = http.cookiejar.MozillaCookieJar()
            cj.load(cf, ignore_discard=True, ignore_expires=True)
            cookie_pairs = [f"{c.name}={c.value}" for c in cj if c.value]
            if cookie_pairs:
                headers["Cookie"] = "; ".join(cookie_pairs)
            for cookie in cj:
                if cookie.name == "VISITOR_INFO1_LIVE":
                    headers["X-Goog-Visitor-Id"] = cookie.value
                    break
        except Exception:
            pass

    return headers


def _build_opener(cookies_file: str | None = None, proxy: str | None = None):
    """Build urllib opener with cookies and proxy support."""
    handlers = []
    cf = _find_cookies(cookies_file)
    if cf:
        try:
            cj = http.cookiejar.MozillaCookieJar()
            cj.load(cf, ignore_discard=True, ignore_expires=True)
            handlers.append(urllib.request.HTTPCookieProcessor(cj))
        except Exception:
            pass
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def fetch_player_response(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    client: dict | None = None,
    po_token: str | None = None,
) -> dict:
    """
    Fetch the player response JSON via YouTube's innertube API.

    Parameters
    ----------
    video_id : str
        YouTube video ID.
    cookies_file : str | None
        Path to Netscape-format cookies_file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.
    client : dict | None
        Override client config.
    po_token : str | None
        PoToken for bot verification bypass.

    Returns
    -------
    dict
        The full player response JSON with streamingData.
    """
    if client:
        profiles = [client]
    else:
        profiles = [
            dict(_DEFAULT_CLIENT),
            {"clientName": "WEB", "clientVersion": "2.20241001.01.00", "hl": "en", "gl": "US"},
        ]

    opener = _build_opener(cookies_file, proxy)
    last_response = {}

    for profile in profiles:
        body = {
            "videoId": video_id,
            "context": {
                "client": profile,
            },
        }

        if po_token:
            body["params"] = "2AMEFdEtp8LaSRkgM6vJk66AKvGjJQDz0qFhYnVwWS1KQlJhU0pM"
            body["cpn"] = "default"

        headers = _build_headers(cookies_file)
        if po_token:
            headers["X-PoToken"] = po_token

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            _INNERTUBE_URL,
            data=data,
            headers=headers,
            method="POST",
        )

        try:
            resp = opener.open(req, timeout=timeout)
            response_data = json.loads(resp.read().decode("utf-8"))
            resp.close()
            last_response = response_data
            sd = response_data.get("streamingData", {})
            fmts = sd.get("formats", []) + sd.get("adaptiveFormats", [])
            has_urls = any("url" in f for f in fmts)
            if has_urls:
                return response_data
        except Exception:
            continue

    return last_response


def is_available() -> bool:
    """Check if innertube API is reachable (network test)."""
    try:
        req = urllib.request.Request(
            _INNERTUBE_URL,
            data=json.dumps({"context": {"client": _DEFAULT_CLIENT}, "videoId": "dQw4w9WgXcQ"}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST",
        )
        opener = urllib.request.build_opener()
        resp = opener.open(req, timeout=10)
        resp.close()
        return True
    except Exception:
        return False
