"""
innertube.py - YouTube internal API client.

Uses YouTube's private innertube API (youtubei/v1/player) to fetch
streaming data directly, avoiding HTML scraping. URLs come pre-signed
— no cipher decryption needed.

This is the same approach yt-dlp uses, providing better rate-limit
resistance since it requires only one API call per video.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
import http.cookiejar
from typing import Any

# Default innertube client config
_DEFAULT_CLIENT = {
    "clientName": "WEB",
    "clientVersion": "2.20241001.01.00",
    "hl": "en",
    "gl": "US",
}

# Innertube API endpoint
_INNERTUBE_URL = "https://www.youtube.com/youtubei/v1/player"


def _build_headers(cookies_file: str | None = None) -> dict[str, str]:
    """Build headers for innertube API requests."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://www.youtube.com",
        "Referer": "https://www.youtube.com/",
        "X-YouTube-Client-Name": "1",
        "X-YouTube-Client-Version": _DEFAULT_CLIENT["clientVersion"],
    }

    # Extract visitorId from cookies if available
    if cookies_file and os.path.isfile(cookies_file):
        try:
            cj = http.cookiejar.MozillaCookieJar()
            cj.load(cookies_file, ignore_discard=True, ignore_expires=True)
            for cookie in cj:
                if cookie.name == "VISITOR_INFO1_LIVE":
                    headers["X-Goog-Visitor-Id"] = cookie.value
                    break
        except Exception:
            pass

    return headers


def _build_request_body(video_id: str, client: dict | None = None) -> dict:
    """Build the innertube API request body."""
    client = client or _DEFAULT_CLIENT
    return {
        "videoId": video_id,
        "context": {
            "client": {
                "clientName": client.get("clientName", "WEB"),
                "clientVersion": client.get("clientVersion", _DEFAULT_CLIENT["clientVersion"]),
                "hl": client.get("hl", "en"),
                "gl": client.get("gl", "US"),
            },
        },
    }


def _build_opener(cookies_file: str | None = None, proxy: str | None = None):
    """Build urllib opener with cookies and proxy support."""
    import urllib.request

    handlers = []
    if cookies_file:
        cj = http.cookiejar.MozillaCookieJar()
        cj.load(cookies_file, ignore_discard=True, ignore_expires=True)
        handlers.append(urllib.request.HTTPCookieProcessor(cj))
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
        PoToken for bot verification bypass. If not provided,
        the request may be blocked by YouTube.

    Returns
    -------
    dict
        The full player response JSON with streamingData.
    """
    client_config = client or _DEFAULT_CLIENT

    # Build request body with optional PoToken
    body = {
        "videoId": video_id,
        "context": {
            "client": {
                "clientName": client_config.get("clientName", "WEB"),
                "clientVersion": client_config.get("clientVersion", _DEFAULT_CLIENT["clientVersion"]),
                "hl": client_config.get("hl", "en"),
                "gl": client_config.get("gl", "US"),
            },
        },
    }

    # Add PoToken if available
    if po_token:
        body["params"] = "2AMEFdEtp8LaSRkgM6vJk66AKvGjJQDz0qFhYnVwWS1KQlJhU0pM"
        body["cpn"] = "default"
        # PoToken goes in the request context
        body.setdefault("context", {}).setdefault("client", {})

    headers = _build_headers(cookies_file)
    headers["X-Goog-AuthUser"] = "0"

    if po_token:
        headers["X-PoToken"] = po_token

    data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        _INNERTUBE_URL,
        data=data,
        headers=headers,
        method="POST",
    )

    opener = _build_opener(cookies_file, proxy)
    resp = opener.open(req, timeout=timeout)
    response_data = json.loads(resp.read().decode("utf-8"))
    resp.close()

    return response_data


def is_available() -> bool:
    """Check if innertube API is reachable (network test)."""
    try:
        req = urllib.request.Request(
            "https://www.youtube.com/youtubei/v1/player",
            data=json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": "1"}}, "videoId": "test"}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST",
        )
        opener = urllib.request.build_opener()
        resp = opener.open(req, timeout=10)
        resp.close()
        return True
    except Exception:
        return False
