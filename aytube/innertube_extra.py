"""
Innertube API helper for playlist and related videos.
Uses YouTube's private API to bypass obfuscated HTML keys.
"""
import json
import os
import urllib.request
import urllib.error


def _build_opener(cookies_file=None, proxy=None):
    """Build urllib opener with cookies and proxy."""
    from .fetcher import _build_opener
    return _build_opener(cookies_file=cookies_file, proxy=proxy)


def _build_headers(cookies_file=None):
    """Build headers for innertube requests."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://www.youtube.com",
        "Referer": "https://www.youtube.com/",
        "X-YouTube-Client-Name": "1",
        "X-YouTube-Client-Version": "2.20241001.01.00",
    }

    if cookies_file and os.path.isfile(cookies_file):
        try:
            import http.cookiejar
            cj = http.cookiejar.MozillaCookieJar()
            cj.load(cookies_file, ignore_discard=True, ignore_expires=True)
            for cookie in cj:
                if cookie.name == "VISITOR_INFO1_LIVE":
                    headers["X-Goog-Visitor-Id"] = cookie.value
                    break
        except Exception:
            pass

    return headers


def fetch_playlist(playlist_id, cookies_file=None, proxy=None, timeout=30, max_results=100):
    """Fetch playlist videos using Innertube API."""
    opener = _build_opener(cookies_file=cookies_file, proxy=proxy)
    headers = _build_headers(cookies_file=cookies_file)

    body = {
        "browseId": f"VL{playlist_id}",
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20241001.01.00",
                "hl": "en",
                "gl": "US"
            }
        },
        "params": "wAEB",
    }

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        "https://www.youtube.com/youtubei/v1/browse",
        data=data,
        headers=headers,
    )

    resp = opener.open(req, timeout=timeout)
    api_data = json.loads(resp.read().decode("utf-8"))

    # Try to find video items anywhere in response
    found = []
    def find_videos(obj, depth=0):
        if depth > 8 or len(found) >= max_results:
            return
        if isinstance(obj, dict):
            vid = obj.get("videoId") or obj.get("id", "")
            if isinstance(vid, str) and len(vid) == 11:
                found.append(obj)
                return
            for v in obj.values():
                find_videos(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                find_videos(item, depth + 1)

    find_videos(api_data)

    if found:
        videos = []
        seen = set()
        for vr in found:
            video_id = vr.get("videoId", "") or vr.get("id", "")
            if not video_id or video_id in seen or len(video_id) != 11:
                continue
            seen.add(video_id)
            title = _deep_find_text(vr)
            thumb = _deep_find_thumb(vr)
            videos.append({
                "video_id": video_id,
                "title": title or f"Video {video_id}",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "position": str(len(videos) + 1),
                "thumbnail": thumb,
            })
        print(f"  Innertube playlist: found {len(videos)} videos")
        return videos[:max_results]

    return []


def fetch_related(video_id, cookies_file=None, proxy=None, timeout=30, max_results=20):
    """Fetch related videos using Innertube API."""
    opener = _build_opener(cookies_file=cookies_file, proxy=proxy)
    headers = _build_headers(cookies_file=cookies_file)

    body = {
        "videoId": video_id,
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20241001.01.00",
                "hl": "en",
                "gl": "US"
            }
        },
    }

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        "https://www.youtube.com/youtubei/v1/next",
        data=data,
        headers=headers,
    )

    resp = opener.open(req, timeout=timeout)
    api_data = json.loads(resp.read().decode("utf-8"))

    return _parse_related_response(api_data, max_results)


def _parse_playlist_response(data, max_results):
    """Parse Innertube playlist response."""
    videos = []
    seen = set()

    def _deep_find_text(obj):
        if isinstance(obj, dict):
            for k in ("simpleText", "text", "content"):
                if k in obj and isinstance(obj[k], str):
                    return obj[k]
            runs = obj.get("runs", [])
            if runs and isinstance(runs[0], dict):
                t = runs[0].get("text", "")
                if t:
                    return t
            for v in obj.values():
                r = _deep_find_text(v)
                if r:
                    return r
        elif isinstance(obj, list):
            for item in obj:
                r = _deep_find_text(item)
                if r:
                    return r
        return ""

    def _deep_find_thumb(obj):
        if isinstance(obj, dict):
            for k in ("thumbnail", "thumbnails"):
                val = obj.get(k)
                if isinstance(val, dict):
                    thumbs = val.get("thumbnails", [])
                    if thumbs:
                        return thumbs[-1].get("url", "")
                elif isinstance(val, list) and val:
                    last = val[-1]
                    if isinstance(last, dict):
                        return last.get("url", "")
            for v in obj.values():
                r = _deep_find_thumb(v)
                if r:
                    return r
        elif isinstance(obj, list):
            for item in obj:
                r = _deep_find_thumb(item)
                if r:
                    return r
        return ""

    def _extract_item(vr):
        video_id = vr.get("videoId", "") or vr.get("id", "")
        if not video_id or video_id in seen or len(video_id) != 11:
            return
        seen.add(video_id)
        title = _deep_find_text(vr)
        thumb = _deep_find_thumb(vr)
        videos.append({
            "video_id": video_id,
            "title": title or f"Video {video_id}",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "position": str(len(videos) + 1),
            "thumbnail": thumb,
        })

    def walk(obj):
        if len(videos) >= max_results:
            return
        if isinstance(obj, dict):
            vid = obj.get("videoId") or obj.get("id", "")
            if isinstance(vid, str) and len(vid) == 11:
                _extract_item(obj)
                return
            for rtype in ("playlistVideoRenderer", "videoRenderer", "gridVideoRenderer",
                          "compactVideoRenderer", "reelItemRenderer",
                          "videoWithContextRenderer", "playlistPanelVideoRenderer"):
                if rtype in obj:
                    vr = obj[rtype]
                    if rtype == "videoWithContextRenderer":
                        vr = vr.get("compactVideoRenderer", vr)
                    elif rtype == "reelItemRenderer":
                        vr = vr.get("info", {}).get("videoRenderer", vr)
                    _extract_item(vr)
                    return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return videos


def _parse_related_response(data, max_results):
    """Parse Innertube next/related response."""
    videos = []
    seen = set()

    def _deep_find_text(obj):
        if isinstance(obj, dict):
            for k in ("simpleText", "text", "content"):
                if k in obj and isinstance(obj[k], str):
                    return obj[k]
            runs = obj.get("runs", [])
            if runs and isinstance(runs[0], dict):
                t = runs[0].get("text", "")
                if t:
                    return t
            for v in obj.values():
                r = _deep_find_text(v)
                if r:
                    return r
        elif isinstance(obj, list):
            for item in obj:
                r = _deep_find_text(item)
                if r:
                    return r
        return ""

    def _deep_find_thumb(obj):
        if isinstance(obj, dict):
            for k in ("thumbnail", "thumbnails"):
                val = obj.get(k)
                if isinstance(val, dict):
                    thumbs = val.get("thumbnails", [])
                    if thumbs:
                        return thumbs[-1].get("url", "")
                elif isinstance(val, list) and val:
                    last = val[-1]
                    if isinstance(last, dict):
                        return last.get("url", "")
            for v in obj.values():
                r = _deep_find_thumb(v)
                if r:
                    return r
        elif isinstance(obj, list):
            for item in obj:
                r = _deep_find_thumb(item)
                if r:
                    return r
        return ""

    def _parse_renderer(vr):
        video_id = vr.get("videoId", "")
        if not video_id or video_id in seen or len(video_id) != 11:
            return None
        seen.add(video_id)
        title = _deep_find_text(vr)
        thumb = _deep_find_thumb(vr)
        length = vr.get("lengthText", {}).get("simpleText", "")
        if not length:
            length = vr.get("lengthSeconds", "")
        views = vr.get("viewCountText", {}).get("simpleText", "")
        if not views:
            views = vr.get("shortViewCountText", {}).get("simpleText", "")
        channel = ""
        for key in ("longBylineText", "shortBylineText", "ownerText"):
            runs = vr.get(key, {}).get("runs", [])
            if runs:
                channel = runs[0].get("text", "")
                break
        return {
            "video_id": video_id,
            "title": title or f"Video {video_id}",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "channel": channel,
            "thumbnail": thumb,
            "duration": length,
            "view_count": views,
        }

    def walk(obj):
        if len(videos) >= max_results:
            return
        if isinstance(obj, dict):
            vid = obj.get("videoId", "")
            if isinstance(vid, str) and len(vid) == 11:
                v = _parse_renderer(obj)
                if v:
                    videos.append(v)
                return
            for rtype in ("compactVideoRenderer", "videoWithContextRenderer",
                          "videoRenderer", "gridVideoRenderer", "reelItemRenderer",
                          "playlistVideoRenderer"):
                if rtype in obj:
                    vr = obj[rtype]
                    if rtype == "videoWithContextRenderer":
                        vr = vr.get("compactVideoRenderer", vr)
                    elif rtype == "reelItemRenderer":
                        vr = vr.get("info", {}).get("videoRenderer", vr)
                    v = _parse_renderer(vr)
                    if v:
                        videos.append(v)
                    return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    # Navigate to secondaryResults
    contents = data.get("contents", {})
    two_col = contents.get("twoColumnWatchNextResults", {})
    secondary = two_col.get("secondaryResults", {})
    renderer = secondary.get("secondaryResultsRenderer", {})
    items = renderer.get("contents", [])

    if items:
        for item in items:
            walk(item)

    if not videos:
        walk(data)

    return videos[:max_results]
