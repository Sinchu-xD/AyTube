"""
Thumbnail download for YouTube videos.
"""
from __future__ import annotations

import os
import urllib.request
import http.cookiejar


def get_thumbnails(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> list[dict]:
    """
    Get all available thumbnail URLs for a YouTube video.

    Parameters
    ----------
    video_id : str
        YouTube video ID.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    list[dict]
        List of thumbnail dicts with: url, width, height, type.
    """
    # YouTube provides these standard thumbnail sizes
    base_url = f"https://i.ytimg.com/vi/{video_id}"
    thumbnails = [
        {"url": f"{base_url}/default.jpg", "width": 120, "height": 90, "type": "default"},
        {"url": f"{base_url}/mqdefault.jpg", "width": 320, "height": 180, "type": "medium"},
        {"url": f"{base_url}/hqdefault.jpg", "width": 480, "height": 360, "type": "high"},
        {"url": f"{base_url}/sddefault.jpg", "width": 640, "height": 480, "type": "standard"},
        {"url": f"{base_url}/maxresdefault.jpg", "width": 1280, "height": 720, "type": "maxres"},
        {"url": f"{base_url}/hq720.jpg", "width": 1280, "height": 720, "type": "hq720"},
        {"url": f"{base_url}/sd480.jpg", "width": 854, "height": 480, "type": "sd480"},
    ]

    # Also try webp versions
    webp_thumbnails = []
    for t in thumbnails:
        webp_url = t["url"].replace("/vi/", "/vi_webp/").rsplit(".", 1)[0] + ".webp"
        webp_thumbnails.append({
            "url": webp_url,
            "width": t["width"],
            "height": t["height"],
            "type": t["type"] + "_webp",
        })

    return thumbnails + webp_thumbnails


def download_thumbnail(
    video_id: str,
    output: str | None = None,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    prefer_webp: bool = False,
) -> str:
    """
    Download the highest quality thumbnail for a YouTube video.

    Parameters
    ----------
    video_id : str
        YouTube video ID.
    output : str | None
        Output file path. If None, uses video_id.jpg.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.
    prefer_webp : bool
        If True, prefer WebP format.

    Returns
    -------
    str
        Path to the downloaded thumbnail.
    """
    import os

    thumbnails = get_thumbnails(video_id, cookies_file, proxy, timeout)

    # Prefer maxres, then hq720
    preferred_types = ["maxres", "hq720", "maxres_webp"] if prefer_webp else ["maxres", "maxres_webp", "hq720"]

    best = None
    for ptype in preferred_types:
        for t in thumbnails:
            if t["type"] == ptype:
                best = t
                break
        if best:
            break

    if not best:
        # Fallback to hqdefault
        for t in thumbnails:
            if t["type"] in ("high", "hq720"):
                best = t
                break

    if not best:
        best = thumbnails[0]  # default

    # Determine output path
    if not output:
        ext = ".webp" if "webp" in best["type"] else ".jpg"
        output = f"{video_id}{ext}"

    # Ensure output directory exists
    out_dir = os.path.dirname(output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Build opener
    handlers = []
    if cookies_file:
        cj = http.cookiejar.MozillaCookieJar()
        cj.load(cookies_file, ignore_discard=True, ignore_expires=True)
        handlers.append(urllib.request.HTTPCookieProcessor(cj))
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))

    opener = urllib.request.build_opener(*handlers)

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.youtube.com/",
    }

    req = urllib.request.Request(best["url"], headers=headers)
    resp = opener.open(req, timeout=timeout)

    with open(output, "wb") as f:
        f.write(resp.read())

    resp.close()
    return output
