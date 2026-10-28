"""
aytube.innertube - YouTube internal API client (v1/player, browse, next).

Direct access to YouTube's client endpoints without deciphering overhead.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import urllib.error
import urllib.request
from typing import Any

from .utils import build_opener, find_cookies_path

_INNERTUBE_URL = "https://www.youtube.com/youtubei/v1/player"
_BROWSE_URL = "https://www.youtube.com/youtubei/v1/browse"
_NEXT_URL = "https://www.youtube.com/youtubei/v1/next"

# Client profiles for Innertube
CLIENT_PROFILES = {
    "ANDROID_VR": {
        "clientName": "ANDROID_VR",
        "clientVersion": "1.56.21",
        "deviceModel": "Quest 3",
        "hl": "en",
        "gl": "US",
    },
    "WEB": {
        "clientName": "WEB",
        "clientVersion": "2.20241001.01.00",
        "hl": "en",
        "gl": "US",
    },
    "IOS": {
        "clientName": "IOS",
        "clientVersion": "19.29.1",
        "deviceModel": "iPhone16,2",
        "hl": "en",
        "gl": "US",
    },
    "TV": {
        "clientName": "TVHTML5",
        "clientVersion": "7.20241001.00.00",
        "hl": "en",
        "gl": "US",
    },
}


def _build_api_headers(cookies_file: str | None = None) -> dict[str, str]:
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

    cf = find_cookies_path(cookies_file)
    if cf and os.path.isfile(cf):
        try:
            cj = http.cookiejar.MozillaCookieJar()
            cj.load(cf, ignore_discard=True, ignore_expires=True)
            cookie_pairs = [f"{c.name}={c.value}" for c in cj if c.value]
            if cookie_pairs:
                headers["Cookie"] = "; ".join(cookie_pairs)
            for c in cj:
                if c.name == "VISITOR_INFO1_LIVE":
                    headers["X-Goog-Visitor-Id"] = c.value
                    break
        except Exception:
            pass

    return headers


def fetch_player_response(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    client: dict | None = None,
    po_token: str | None = None,
) -> dict:
    """
    Fetch player response JSON with direct streamingData formats.
    """
    profiles = [client] if client else [
        CLIENT_PROFILES["ANDROID_VR"],
        CLIENT_PROFILES["WEB"],
        CLIENT_PROFILES["IOS"],
    ]

    opener = build_opener(cookies_file, proxy)
    last_response: dict = {}

    for profile in profiles:
        body: dict[str, Any] = {
            "videoId": video_id,
            "context": {
                "client": profile,
            },
        }

        if po_token:
            body["params"] = "2AMEFdEtp8LaSRkgM6vJk66AKvGjJQDz0qFhYnVwWS1KQlJhU0pM"
            body["cpn"] = "default"

        headers = _build_api_headers(cookies_file)
        if po_token:
            headers["X-PoToken"] = po_token

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(_INNERTUBE_URL, data=data, headers=headers, method="POST")

        try:
            resp = opener.open(req, timeout=timeout)
            response_data = json.loads(resp.read().decode("utf-8"))
            resp.close()
            last_response = response_data
            sd = response_data.get("streamingData", {})
            fmts = sd.get("formats", []) + sd.get("adaptiveFormats", [])
            if any("url" in f for f in fmts):
                return response_data
        except Exception:
            continue

    return last_response


def fetch_playlist(
    playlist_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    max_results: int = 100,
) -> list[dict]:
    """
    Fetch videos belonging to a playlist via Innertube browse API.
    """
    clean_id = playlist_id.replace("VL", "")
    browse_id = f"VL{clean_id}"

    opener = build_opener(cookies_file, proxy)
    headers = _build_api_headers(cookies_file)
    headers["X-YouTube-Client-Name"] = "1"
    headers["X-YouTube-Client-Version"] = "2.20241001.01.00"

    body = {
        "browseId": browse_id,
        "context": {
            "client": CLIENT_PROFILES["WEB"],
        },
        "params": "wAEB",
    }

    try:
        req = urllib.request.Request(_BROWSE_URL, data=json.dumps(body).encode("utf-8"), headers=headers)
        resp = opener.open(req, timeout=timeout)
        data = json.loads(resp.read().decode("utf-8"))
        resp.close()
    except Exception:
        return []

    videos: list[dict] = []
    seen: set[str] = set()

    def walk(obj: Any):
        if len(videos) >= max_results:
            return
        if isinstance(obj, dict):
            vid = obj.get("videoId") or obj.get("id", "")
            if isinstance(vid, str) and len(vid) == 11 and vid not in seen:
                title = _find_text(obj)
                thumb = _find_thumb(obj)
                seen.add(vid)
                videos.append({
                    "video_id": vid,
                    "title": title or f"Video {vid}",
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "position": len(videos) + 1,
                    "thumbnail": thumb,
                })
                return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return videos[:max_results]


def fetch_related(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    max_results: int = 20,
) -> list[dict]:
    """
    Fetch related/recommended videos for a given video ID via Innertube next API.
    """
    opener = build_opener(cookies_file, proxy)
    headers = _build_api_headers(cookies_file)

    body = {
        "videoId": video_id,
        "context": {
            "client": CLIENT_PROFILES["WEB"],
        },
    }

    try:
        req = urllib.request.Request(_NEXT_URL, data=json.dumps(body).encode("utf-8"), headers=headers)
        resp = opener.open(req, timeout=timeout)
        data = json.loads(resp.read().decode("utf-8"))
        resp.close()
    except Exception:
        return []

    videos: list[dict] = []
    seen: set[str] = set()

    def walk(obj: Any):
        if len(videos) >= max_results:
            return
        if isinstance(obj, dict):
            vid = obj.get("videoId")
            if isinstance(vid, str) and len(vid) == 11 and vid not in seen and vid != video_id:
                seen.add(vid)
                title = _find_text(obj)
                thumb = _find_thumb(obj)
                channel = _find_channel(obj)
                length = obj.get("lengthText", {}).get("simpleText", "") or obj.get("lengthSeconds", "")
                views = obj.get("viewCountText", {}).get("simpleText", "") or obj.get("shortViewCountText", {}).get("simpleText", "")
                videos.append({
                    "video_id": vid,
                    "title": title or f"Video {vid}",
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "channel": channel,
                    "thumbnail": thumb,
                    "duration": length,
                    "view_count": views,
                })
                return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return videos[:max_results]


def _find_text(obj: dict) -> str:
    for k in ("title", "simpleText", "text", "content"):
        val = obj.get(k)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict):
            t = _find_text(val)
            if t:
                return t
    runs = obj.get("runs", [])
    if runs and isinstance(runs, list) and isinstance(runs[0], dict):
        return runs[0].get("text", "")
    return ""


def _find_thumb(obj: dict) -> str:
    val = obj.get("thumbnail") or obj.get("thumbnails")
    if isinstance(val, dict):
        thumbs = val.get("thumbnails", [])
        if thumbs and isinstance(thumbs[-1], dict):
            return thumbs[-1].get("url", "")
    elif isinstance(val, list) and val:
        last = val[-1]
        if isinstance(last, dict):
            return last.get("url", "")
    return ""


def _find_channel(obj: dict) -> str:
    for k in ("longBylineText", "shortBylineText", "ownerText"):
        val = obj.get(k)
        if isinstance(val, dict):
            runs = val.get("runs", [])
            if runs and isinstance(runs[0], dict):
                return runs[0].get("text", "")
    return ""


def is_available() -> bool:
    """Test if Innertube endpoint is accessible."""
    try:
        req = urllib.request.Request(
            _INNERTUBE_URL,
            data=json.dumps({"context": {"client": CLIENT_PROFILES["ANDROID_VR"]}, "videoId": "dQw4w9WgXcQ"}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception:
        return False
