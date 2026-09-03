"""
Get YouTube channel information.
"""
from __future__ import annotations

import re
import json
import html as html_module
import urllib.request
import http.cookiejar


def get_channel_info(
    channel_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict:
    """
    Get information about a YouTube channel.

    Parameters
    ----------
    channel_id : str
        Channel ID (starts with UC...) or username.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    dict
        Channel info: channel_id, name, description, subscriber_count,
        video_count, thumbnail, is_verified, is_verified_artist.
    """
    # Build channel URL
    if channel_id.startswith("UC"):
        url = f"https://www.youtube.com/channel/{channel_id}"
    elif channel_id.startswith("@"):
        url = f"https://www.youtube.com/{channel_id}"
    else:
        url = f"https://www.youtube.com/c/{channel_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Referer": "https://www.youtube.com/",
    }

    handlers = []
    if cookies_file:
        cj = http.cookiejar.MozillaCookieJar()
        cj.load(cookies_file, ignore_discard=True, ignore_expires=True)
        handlers.append(urllib.request.HTTPCookieProcessor(cj))
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))

    opener = urllib.request.build_opener(*handlers)
    opener.addheaders = list(headers.items())

    resp = opener.open(url, timeout=timeout)
    page_html = resp.read().decode("utf-8", errors="replace")
    resp.close()

    # Extract ytInitialData
    match = re.search(r'ytInitialData\s*=\s*({.+?});</script>', page_html, re.DOTALL)
    if not match:
        match = re.search(r'ytInitialData\s*=\s*({.+?});', page_html, re.DOTALL)

    if not match:
        return {}

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}

    # Navigate the structure
    def find_channel_info(obj):
        if isinstance(obj, dict):
            # Channel header
            if "channelHeaderRenderer" in obj:
                ch = obj["channelHeaderRenderer"]
                return _parse_channel_header(ch)

            # Microformat data
            if "microformat" in obj:
                mf = obj["microformat"]
                return _parse_microformat(mf)

            for v in obj.values():
                result = find_channel_info(v)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = find_channel_info(item)
                if result:
                    return result
        return None

    info = find_channel_info(data) or {}

    # Try to get subscriber count from meta tags
    og_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', page_html)
    if og_title and not info.get("name"):
        info["name"] = html_module.unescape(og_title.group(1))

    return info


def _parse_channel_header(ch: dict) -> dict:
    """Parse channel header data."""
    info = {}

    # Channel name
    title = ch.get("title", {})
    if isinstance(title, dict):
        info["name"] = title.get("simpleText", "")

    # Description
    desc = ch.get("description", {})
    if isinstance(desc, dict):
        info["description"] = desc.get("simpleText", "")

    # Subscriber count
    subs = ch.get("subscriberCountText", {})
    if isinstance(subs, dict):
        info["subscriber_count"] = subs.get("simpleText", "")
        info["subscriber_count_parsed"] = _parse_count(subs.get("simpleText", "0"))

    # Video count
    videos = ch.get("videoCountText", {})
    if isinstance(videos, dict):
        info["video_count"] = videos.get("simpleText", "")

    # Thumbnail
    thumbs = ch.get("avatar", {}).get("thumbnails", [])
    if thumbs:
        info["thumbnail"] = thumbs[-1].get("url", "")

    # Verification badges
    badges = ch.get(" badges", [])
    for badge in badges:
        if isinstance(badge, dict):
            tooltip = badge.get("metadataBadgeRenderer", {}).get("tooltip", "").lower()
            info["is_verified"] = info.get("is_verified", False) or "verified" in tooltip
            info["is_verified_artist"] = info.get("is_verified_artist", False) or "artist" in tooltip

    return info


def _parse_microformat(mf: dict) -> dict:
    """Parse microformat data."""
    info = {}
    mf_data = mf.get("microformatDataRenderer", {})

    if mf_data:
        info["url"] = mf_data.get("urlCanonical", "")
        info["description"] = mf_data.get("description", {}).get("simpleText", "") if isinstance(mf_data.get("description"), dict) else ""

    return info


def _parse_count(count_str: str) -> int:
    """Parse count string like '1.2M' to int."""
    count_str = count_str.strip().upper()
    if not count_str:
        return 0

    multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}
    for suffix, mult in multipliers.items():
        if suffix in count_str:
            try:
                return int(float(count_str.replace(suffix, "").strip()) * mult)
            except ValueError:
                return 0

    try:
        return int(count_str.replace(",", "").replace(" ", ""))
    except ValueError:
        return 0


def get_channel_avatar(
    channel_id: str,
    output: str | None = None,
    size: str = "high",  # "default", "medium", "high"
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> str:
    """
    Download channel avatar/icon.

    Parameters
    ----------
    channel_id : str
        Channel ID or username.
    output : str | None
        Output file path. If None, uses channel_id.jpg.
    size : str
        Size preference: "default", "medium", "high".
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    str
        Path to downloaded avatar.
    """
    import os

    info = get_channel_info(channel_id, cookies_file, proxy, timeout)
    thumbnail_url = info.get("thumbnail", "")

    if not thumbnail_url:
        raise ValueError(f"Could not find avatar for channel: {channel_id}")

    if not output:
        safe_name = channel_id.replace("/", "_").replace("@", "")
        output = f"{safe_name}_avatar.jpg"

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

    req = urllib.request.Request(thumbnail_url, headers=headers)
    resp = opener.open(req, timeout=timeout)

    with open(output, "wb") as f:
        f.write(resp.read())

    resp.close()
    return output
