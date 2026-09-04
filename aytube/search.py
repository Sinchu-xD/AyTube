"""
Search YouTube videos by query.

Uses YouTube's search suggestions API to find videos.
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.parse
import http.cookiejar


def search(
    query: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    max_results: int = 20,
) -> list[dict]:
    """
    Search YouTube videos.

    Parameters
    ----------
    query : str
        Search query string.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.
    max_results : int
        Maximum number of results to return.

    Returns
    -------
    list[dict]
        List of video results with: video_id, title, url, channel,
        channel_id, thumbnail, duration, view_count, description.
    """
    # Use YouTube's search page
    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)

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

    resp = opener.open(search_url, timeout=timeout)
    html = resp.read().decode("utf-8", errors="replace")
    resp.close()

    # Extract ytInitialData - YouTube search pages can have this anywhere
    # The JSON can be very large, so we grab from ytInitialData to the end of script tag or next semicolon
    data = None

    # Strategy 1: Match everything after ytInitialData =
    m = re.search(r'ytInitialData\s*=\s*({.+)\s*</script>', html, re.DOTALL)
    if m:
        json_str = m.group(1)
        # The JSON might have a trailing semicolon before </script>
        json_str = re.sub(r';\s*$', '', json_str)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Strategy 2: Try simpler match (whole object in one script tag)
    if not data:
        m = re.search(r'ytInitialData\s*=\s*({.+?});\s*</script>', html, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

    if not data:
        # Strategy 3: try extracting via regex capturing a closing brace before semicolon
        m = re.search(r'ytInitialData\s*=\s*({[^{}]*(?:{[^{}]*}[^{}]*)*+);', html)
        if m:
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

    if not data:
        return []

    # Navigate the structure to find video results
    videos = []

    def extract_videos(obj, depth=0):
        if isinstance(obj, dict):
            if "videoRenderer" in obj:
                vr = obj["videoRenderer"]
                video_id = vr.get("videoId", "")
                title_runs = vr.get("title", {}).get("runs", [])
                title = title_runs[0].get("text", "") if title_runs else ""

                channel_runs = vr.get("longBylineText", {}).get("runs", [])
                channel_name = channel_runs[0].get("text", "") if channel_runs else ""
                channel_id = ""
                if channel_runs:
                    nav = channel_runs[0].get("navigationEndpoint", {})
                    channel_id = nav.get("browseEndpoint", {}).get("browseId", "")

                thumb_runs = vr.get("thumbnail", {}).get("thumbnails", [])
                thumbnail = thumb_runs[-1].get("url", "") if thumb_runs else ""

                length = vr.get("lengthText", {}).get("simpleText", "")
                views = vr.get("viewCountText", {}).get("simpleText", "")
                desc = vr.get("descriptionSnippet", {}).get("runs", [])
                description = desc[0].get("text", "") if desc else ""

                if video_id:
                    videos.append({
                        "video_id": video_id,
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "channel": channel_name,
                        "channel_id": channel_id,
                        "thumbnail": thumbnail,
                        "duration": length,
                        "view_count": views,
                        "description": description,
                    })

                    if len(videos) >= max_results:
                        return

            for v in obj.values():
                extract_videos(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                extract_videos(item, depth + 1)

    extract_videos(data)

    return videos
