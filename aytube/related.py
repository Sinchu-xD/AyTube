"""
Extract related/suggested videos from a YouTube video page.
YouTube jaisa smart suggestion — current video ke basis pe suggestions.
"""
from __future__ import annotations

import re
import json


def _extract_all_json(html: str) -> list[dict]:
    """Extract all top-level JSON objects from HTML."""
    results = []
    depth = 0
    in_string = False
    escape = False
    brace_start = -1

    i = 0
    while i < len(html):
        ch = html[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == '\\' and in_string:
            escape = True
            i += 1
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            i += 1
            continue
        if in_string:
            i += 1
            continue

        if ch == '{':
            if depth == 0:
                brace_start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and brace_start >= 0:
                json_str = html[brace_start:i + 1]
                try:
                    data = json.loads(json_str)
                    results.append(data)
                except json.JSONDecodeError:
                    pass
                brace_start = -1
        i += 1

    return results


def get_related_videos(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    max_results: int = 20,
) -> list[dict]:
    """
    Get related/suggested videos from a YouTube video page.

    Returns list of dicts with: video_id, title, url, channel, thumbnail, duration, view_count.
    """
    from .fetcher import fetch_page

    html = fetch_page(video_id, cookies_file=cookies_file, proxy=proxy, timeout=timeout)

    # Extract all JSON blobs from the page
    json_blobs = _extract_all_json(html)

    # Strategy 1: ytInitialData -> twoColumnWatchNextResults -> secondaryResults
    videos = _from_yt_initial_data(html, json_blobs, max_results)
    if videos:
        return videos

    # Strategy 2: ytInitialPlayerResponse -> watchNextResults
    videos = _from_player_response(html, max_results)
    if videos:
        return videos

    # Strategy 3: Innertube API (bypasses obfuscated HTML keys)
    try:
        from .innertube_extra import fetch_related
        videos = fetch_related(video_id, cookies_file=cookies_file, proxy=proxy,
                               timeout=timeout, max_results=max_results)
        if videos:
            return videos
    except Exception:
        pass

    # Strategy 4: Deep recursive search in all JSON blobs
    return _deep_search(json_blobs, max_results)


def _from_yt_initial_data(html: str, json_blobs: list, max_results: int) -> list[dict]:
    """Extract from ytInitialData modern structure."""

    def extract_from_data(data: dict) -> list[dict]:
        """Try to extract related videos from a JSON data dict."""
        # Modern: twoColumnWatchNextResults.secondaryResults.secondaryResultsRenderer.contents[]
        contents = data.get("contents", {})
        two_col = contents.get("twoColumnWatchNextResults", {})
        secondary = two_col.get("secondaryResults", {})
        renderer = secondary.get("secondaryResultsRenderer", {})
        items = renderer.get("contents", [])

        if items:
            return _extract_items(items, max_results)

        # Broader recursive search in the data
        return _deep_search(data, max_results)

    # Try each JSON blob
    for data in json_blobs:
        videos = extract_from_data(data)
        if videos:
            return videos

    return []


def _from_player_response(html: str, max_results: int) -> list[dict]:
    """Extract from ytInitialPlayerResponse watchNextResults."""
    match = re.search(r'ytInitialPlayerResponse\s*=\s*', html)
    if not match:
        return []

    brace_start = html.find('{', match.end())
    if brace_start == -1:
        return []

    depth = 0
    in_string = False
    escape = False
    json_str = None
    for i in range(brace_start, len(html)):
        ch = html[i]
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                json_str = html[brace_start:i + 1]
                break

    if not json_str:
        return []

    try:
        pr = json.loads(json_str)
    except json.JSONDecodeError:
        return []

    wn = pr.get("watchNextResults", {})
    wnrc = wn.get("watchNextResultsController", {})
    auto = wnrc.get("automaticPlaybackResults", {})
    results = auto.get("results", {})
    items = results.get("contents", [])

    if items:
        return _extract_items(items, max_results)

    items2 = wnrc.get("items", [])
    if items2:
        return _extract_items(items2, max_results)

    return []


def _extract_items(items: list, max_results: int) -> list[dict]:
    """Extract video dicts from a list of renderer items."""
    videos = []
    for item in items:
        if not isinstance(item, dict):
            continue

        # Try each renderer type
        vr = None
        for key in ("compactVideoRenderer", "videoWithContextRenderer",
                     "videoRenderer", "playlistVideoRenderer", "gridVideoRenderer"):
            if key in item:
                vr = item[key]
                if key == "videoWithContextRenderer":
                    vr = vr.get("compactVideoRenderer", vr)
                break

        if vr:
            v = _parse_video(vr)
            if v:
                videos.append(v)
                if len(videos) >= max_results:
                    break

    return videos


def _parse_video(vr: dict) -> dict | None:
    """Parse a video renderer dict into a normalized video info dict."""
    video_id = vr.get("videoId", "")
    if not video_id:
        return None

    # Title - multiple formats
    title = ""
    title_runs = vr.get("title", {}).get("runs", [])
    if title_runs:
        title = title_runs[0].get("text", "")
    elif isinstance(vr.get("title"), str):
        title = vr["title"]
    elif vr.get("headline"):
        title = vr["headline"].get("simpleText", "")

    # Thumbnail - pick largest
    thumb = vr.get("thumbnail", {}).get("thumbnails", [])
    thumbnail = thumb[-1].get("url", "") if thumb else ""

    # Duration
    length = vr.get("lengthText", {}).get("simpleText", "")
    if not length:
        length = vr.get("lengthSeconds", "")

    # Views
    views = vr.get("viewCountText", {}).get("simpleText", "")
    if not views:
        views = vr.get("shortViewCountText", {}).get("simpleText", "")

    # Channel name
    channel = ""
    for key in ("longBylineText", "shortBylineText", "ownerText", "channelName"):
        runs = vr.get(key, {}).get("runs", [])
        if runs:
            channel = runs[0].get("text", "")
            break
        simple = vr.get(key, {}).get("simpleText", "")
        if simple:
            channel = simple
            break

    # Published time
    published = vr.get("publishedTimeText", {}).get("simpleText", "")

    # Badges (LIVE, NEW, etc.)
    badges = []
    for badge in vr.get("badges", []):
        label = badge.get("metadataBadgeRenderer", {}).get("label", "")
        if label:
            badges.append(label)

    return {
        "video_id": video_id,
        "title": title or f"Video {video_id}",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "channel": channel,
        "thumbnail": thumbnail,
        "duration": length,
        "view_count": views,
        "published": published,
        "badges": badges,
    }


def _navigate_and_extract(obj, max_results: int) -> list[dict]:
    """Deep search through nested data for video renderers."""
    videos = []
    seen = set()

    def walk(node):
        if len(videos) >= max_results:
            return
        if isinstance(node, dict):
            # Check all renderer types
            for key in ("compactVideoRenderer", "videoWithContextRenderer",
                         "videoRenderer", "playlistVideoRenderer", "gridVideoRenderer"):
                if key in node:
                    vr = node[key]
                    if key == "videoWithContextRenderer":
                        vr = vr.get("compactVideoRenderer", vr)
                    v = _parse_video(vr)
                    if v and v["video_id"] not in seen:
                        seen.add(v["video_id"])
                        videos.append(v)
                        if len(videos) >= max_results:
                            return
                    break
            for val in node.values():
                walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    return videos


def _find_json(html: str, var_name: str):
    """Find a JS variable assignment containing JSON, handling nested braces."""
    # Match var_name = { ... }; with proper brace counting
    pattern = rf'{var_name}\s*=\s*'
    idx = html.find(var_name + ' = ')
    if idx == -1:
        idx = html.find(var_name + '= ')
    if idx == -1:
        return None

    # Find opening brace
    brace_start = html.find('{', idx)
    if brace_start == -1:
        return None

    # Count braces to find matching closing brace
    depth = 0
    in_string = False
    escape = False
    for i in range(brace_start, len(html)):
        ch = html[i]
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                json_str = html[brace_start:i + 1]
                # Verify it looks like valid JSON
                try:
                    json.loads(json_str)
                    class Match:
                        def group(self, n):
                            return json_str if n == 1 else ""
                    return Match()
                except json.JSONDecodeError:
                    return None

    return None


def _deep_search(data, max_results: int) -> list[dict]:
    """Search all JSON data for video renderers."""
    videos = []
    seen = set()

    def walk(obj):
        if len(videos) >= max_results:
            return
        if isinstance(obj, dict):
            # Check all renderer types
            for rtype in ("compactVideoRenderer", "videoWithContextRenderer",
                         "videoRenderer", "playlistVideoRenderer", "gridVideoRenderer"):
                if rtype in obj:
                    vr = obj[rtype]
                    if rtype == "videoWithContextRenderer":
                        vr = vr.get("compactVideoRenderer", vr)
                    v = _parse_video(vr)
                    if v and v["video_id"] not in seen:
                        seen.add(v["video_id"])
                        videos.append(v)
                    return
            for val in obj.values():
                walk(val)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    if isinstance(data, list):
        for item in data:
            walk(item)
    else:
        walk(data)

    return videos
