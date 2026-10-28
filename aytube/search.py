"""
aytube.search - YouTube search query parser.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any

from .utils import build_opener


def search(
    query: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """
    Search YouTube videos by keyword or phrase.
    """
    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    opener = build_opener(cookies_file, proxy)
    req = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.youtube.com/",
        },
    )

    try:
        with opener.open(req, timeout=timeout) as resp:
            page_html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    # Extract ytInitialData
    data = None
    m = re.search(r'ytInitialData\s*=\s*({.+?});\s*</script>', page_html, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    if not data:
        m2 = re.search(r'ytInitialData\s*=\s*({.+?});', page_html, re.DOTALL)
        if m2:
            try:
                data = json.loads(m2.group(1))
            except json.JSONDecodeError:
                pass

    if not data:
        return []

    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    def walk(obj: Any):
        if len(results) >= max_results:
            return
        if isinstance(obj, dict):
            if "videoRenderer" in obj:
                vr = obj["videoRenderer"]
                vid = vr.get("videoId")
                if vid and len(vid) == 11 and vid not in seen:
                    seen.add(vid)
                    title = _extract_title(vr)
                    thumb = _extract_thumb(vr)
                    duration = vr.get("lengthText", {}).get("simpleText", "")
                    views = vr.get("viewCountText", {}).get("simpleText", "") or vr.get("shortViewCountText", {}).get("simpleText", "")
                    channel = _extract_channel(vr)
                    results.append({
                        "video_id": vid,
                        "title": title or f"Video {vid}",
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "channel": channel,
                        "thumbnail": thumb,
                        "duration": duration,
                        "view_count": views,
                    })
                return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return results[:max_results]


def _extract_title(vr: dict) -> str:
    title_obj = vr.get("title", {})
    runs = title_obj.get("runs", [])
    if runs and isinstance(runs[0], dict):
        return runs[0].get("text", "")
    return title_obj.get("simpleText", "")


def _extract_thumb(vr: dict) -> str:
    thumbs = vr.get("thumbnail", {}).get("thumbnails", [])
    if thumbs and isinstance(thumbs[-1], dict):
        return thumbs[-1].get("url", "")
    return ""


def _extract_channel(vr: dict) -> str:
    for k in ("longBylineText", "shortBylineText", "ownerText"):
        runs = vr.get(k, {}).get("runs", [])
        if runs and isinstance(runs[0], dict):
            return runs[0].get("text", "")
    return ""
