"""
aytube.metadata - Video metadata, subtitles, chapters, channel information, and thumbnails.
"""

from __future__ import annotations

import html as html_module
import json
import os
import re
import urllib.request
from typing import Any

from .innertube import fetch_related
from .utils import build_opener, extract_video_id, fetch_page, find_cookies_path, format_duration, get_player_response


def get_metadata(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Extract comprehensive video metadata without downloading stream payload.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    page_html = fetch_page(video_id, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
    pr = get_player_response(page_html)

    vd = pr.get("videoDetails", {})
    ps = pr.get("playabilityStatus", {})

    length_sec = int(vd.get("lengthSeconds", 0) or 0)
    thumbs = vd.get("thumbnail", {}).get("thumbnails", [])
    thumbnail = thumbs[-1].get("url") if thumbs else ""

    return {
        "video_id": video_id,
        "title": vd.get("title", ""),
        "description": vd.get("shortDescription", ""),
        "thumbnail": thumbnail,
        "thumbnail_urls": [t.get("url") for t in thumbs if t.get("url")],
        "duration": format_duration(length_sec),
        "duration_seconds": length_sec,
        "view_count": int(vd.get("viewCount", 0) or 0),
        "channel_name": vd.get("author", ""),
        "channel_id": vd.get("channelId", ""),
        "upload_date": vd.get("uploadDate", ""),
        "is_live": vd.get("isLive", False),
        "is_private": vd.get("isPrivate", False),
        "playability_status": ps.get("status", ""),
        "playability_reason": ps.get("reason", ""),
        "keywords": vd.get("keywords", []),
        "is_age_restricted": vd.get("isAgeRestricted", False),
    }


def list_subtitles(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict[str, list[dict[str, Any]]]:
    """
    List available closed caption and subtitle tracks for a video.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    page_html = fetch_page(video_id, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
    pr = get_player_response(page_html)

    captions_data = pr.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
    caption_tracks = captions_data.get("captionTracks", [])

    results: dict[str, list[dict[str, Any]]] = {}
    for track in caption_tracks:
        code = track.get("languageCode", "")
        name = track.get("name", {}).get("simpleText", code)
        t_url = track.get("baseUrl", "")
        is_auto = track.get("kind", "") == "asr"
        is_translated = track.get("isTranslated", False)

        if code not in results:
            results[code] = []

        results[code].append({
            "url": t_url,
            "lang": code,
            "lang_name": name,
            "is_auto": is_auto,
            "is_translated": is_translated,
        })

    return results


def get_thumbnails(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """
    Return all standard YouTube image resolution variants for video thumbnail.
    """
    vid = extract_video_id(video_id) or video_id
    base_url = f"https://i.ytimg.com/vi/{vid}"
    standard = [
        {"url": f"{base_url}/default.jpg", "width": 120, "height": 90, "type": "default"},
        {"url": f"{base_url}/mqdefault.jpg", "width": 320, "height": 180, "type": "medium"},
        {"url": f"{base_url}/hqdefault.jpg", "width": 480, "height": 360, "type": "high"},
        {"url": f"{base_url}/sddefault.jpg", "width": 640, "height": 480, "type": "standard"},
        {"url": f"{base_url}/maxresdefault.jpg", "width": 1280, "height": 720, "type": "maxres"},
        {"url": f"{base_url}/hq720.jpg", "width": 1280, "height": 720, "type": "hq720"},
    ]
    webp = []
    for t in standard:
        webp_url = t["url"].replace("/vi/", "/vi_webp/").rsplit(".", 1)[0] + ".webp"
        webp.append({
            "url": webp_url,
            "width": t["width"],
            "height": t["height"],
            "type": t["type"] + "_webp",
        })
    return standard + webp


def download_thumbnail(
    video_id: str,
    output: str | None = None,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    prefer_webp: bool = False,
) -> str:
    """Download highest resolution thumbnail image to disk."""
    vid = extract_video_id(video_id) or video_id
    thumbs = get_thumbnails(vid, cookies_file, proxy, timeout)

    if prefer_webp:
        preferred = [t["url"] for t in thumbs if "_webp" in t["type"] and ("maxres" in t["type"] or "hq720" in t["type"])]
    else:
        preferred = [t["url"] for t in thumbs if "_webp" not in t["type"] and ("maxres" in t["type"] or "hq720" in t["type"])]

    chosen_url = preferred[0] if preferred else thumbs[-1]["url"]

    if not output:
        ext = "webp" if prefer_webp else "jpg"
        output = f"{vid}_thumb.{ext}"

    opener = build_opener(cookies_file, proxy)
    req = urllib.request.Request(
        chosen_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.youtube.com/"},
    )
    with opener.open(req, timeout=timeout) as resp:
        with open(output, "wb") as f:
            f.write(resp.read())

    return output


def get_chapters(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Extract chapter markers and timestamps from video player or description."""
    vid = extract_video_id(video_id) or video_id
    page_html = fetch_page(vid, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
    pr = get_player_response(page_html)

    # Strategy 1: Attachable chapters in player response
    chapters_data = pr.get("chapters", {})
    if chapters_data:
        items = chapters_data.get("playerAttachableChaptersRenderer", [])
        if items:
            results = []
            for item in items:
                cr = item.get("chapterRenderer", {})
                t = cr.get("title", {}).get("simpleText", "")
                st_ms = cr.get("timeRangeStartMillis", 0)
                sec = int(st_ms // 1000)
                results.append({
                    "title": t,
                    "start_time": sec,
                    "start_time_formatted": format_duration(sec),
                })
            if results:
                return results

    # Strategy 2: Parse description timestamps
    desc = pr.get("videoDetails", {}).get("shortDescription", "")
    ts_pattern = re.compile(r'^(\d{1,2}:)?(\d{1,2}):(\d{2})\s+(.+)', re.MULTILINE)
    parsed_chapters = []
    for m in ts_pattern.finditer(desc):
        h = int(m.group(1)[:-1]) if m.group(1) else 0
        minutes = int(m.group(2))
        sec = int(m.group(3))
        title = m.group(4).strip()
        total_sec = h * 3600 + minutes * 60 + sec
        parsed_chapters.append({
            "title": title,
            "start_time": total_sec,
            "start_time_formatted": format_duration(total_sec),
        })

    return parsed_chapters


def get_related_videos(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Extract recommended related videos for a given video."""
    vid = extract_video_id(video_id) or video_id
    return fetch_related(vid, cookies_file=cookies_file, proxy=proxy, timeout=timeout, max_results=max_results)


def get_channel_info(
    channel_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Fetch channel name, subscriber count, avatar, and description."""
    if channel_id.startswith(("http://", "https://")):
        url = channel_id
    elif channel_id.startswith("UC"):
        url = f"https://www.youtube.com/channel/{channel_id}"
    elif channel_id.startswith("@"):
        url = f"https://www.youtube.com/{channel_id}"
    else:
        url = f"https://www.youtube.com/c/{channel_id}"

    opener = build_opener(cookies_file, proxy)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.youtube.com/",
        },
    )
    with opener.open(req, timeout=timeout) as resp:
        page_html = resp.read().decode("utf-8", errors="replace")

    info: dict[str, Any] = {"channel_id": channel_id, "url": url}

    # Meta tag parsing
    og_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', page_html)
    if og_title:
        info["name"] = html_module.unescape(og_title.group(1))

    og_image = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', page_html)
    if og_image:
        info["thumbnail"] = html_module.unescape(og_image.group(1))

    og_desc = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', page_html)
    if og_desc:
        info["description"] = html_module.unescape(og_desc.group(1))

    # Subscriber count from page text
    sub_m = re.search(r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([^"]+)"\}\},"simpleText":"([^"]+)"\}', page_html)
    if sub_m:
        info["subscriber_count"] = sub_m.group(2)
    else:
        sub_fallback = re.search(r'([\d\.]+[KMB]?\s+subscribers)', page_html)
        if sub_fallback:
            info["subscriber_count"] = sub_fallback.group(1)

    return info


def get_channel_avatar(
    channel_id: str,
    output: str | None = None,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> str:
    """Download channel avatar profile image."""
    info = get_channel_info(channel_id, cookies_file, proxy, timeout)
    thumb_url = info.get("thumbnail")
    if not thumb_url:
        raise ValueError(f"Could not locate avatar for channel: {channel_id}")

    if not output:
        clean_name = channel_id.replace("/", "_").replace("@", "")
        output = f"{clean_name}_avatar.jpg"

    opener = build_opener(cookies_file, proxy)
    req = urllib.request.Request(thumb_url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req, timeout=timeout) as resp:
        with open(output, "wb") as f:
            f.write(resp.read())
    return output


def bypass_age_check(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict[str, Any] | None:
    """Attempt embed player query for age-restricted video streams."""
    vid = extract_video_id(video_id) or video_id
    embed_url = f"https://www.youtube.com/embed/{vid}"
    try:
        html_code = fetch_page(embed_url, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
        pr = get_player_response(html_code)
        sd = pr.get("streamingData", {})
        if sd.get("formats") or sd.get("adaptiveFormats"):
            return pr
    except Exception:
        pass
    return None
