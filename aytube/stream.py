"""
Stream selection and verification.

Filters formats by audio/video type, selects best quality matching
user preferences, and verifies stream URLs are actually reachable
by checking byte ranges.
"""

import re
import os
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# Quality ranking (higher = better)
_QUALITY_RANK = {
    "2160p": 2160, "4k": 2160,
    "1440p": 1440, "2k": 1440,
    "1080p": 1080, "fhd": 1080,
    "720p": 720, "hd": 720,
    "480p": 480, "sd": 480,
    "360p": 360,
    "240p": 240,
    "144p": 144,
    "best": 9999,
    "worst": -1,
}

# Audio-only quality ranking
_AUDIO_RANK = {
    "high": 999, "best": 999, "medium": 500, "low": 100, "worst": -1
}

_ITAG_TYPE_MAP = {
    # Video-only (need separate audio)
    22: ("video", "mp4", "1080p"),
    18: ("video", "mp4", "360p"),
    35: ("video", "flv", "480p"),
    34: ("video", "flv", "360p"),
    59: ("video", "mp4", "480p"),
    78: ("video", "mp4", "480p"),
    37: ("video", "mp4", "1080p"),
    38: ("video", "mp4", "3072p"),
    82: ("video", "mp4", "360p"),
    83: ("video", "mp4", "480p"),
    84: ("video", "mp4", "720p"),
    85: ("video", "mp4", "1080p"),
    100: ("video", "webm", "360p"),
    101: ("video", "webm", "480p"),
    102: ("video", "webm", "720p"),
    133: ("video", "mp4", "240p"),
    134: ("video", "mp4", "360p"),
    135: ("video", "mp4", "480p"),
    136: ("video", "mp4", "720p"),
    137: ("video", "mp4", "1080p"),
    140: ("video", "mp4", "720p"),
    141: ("video", "mp4", "audio"),  # Actually audio but sometimes mapped
    160: ("video", "mp4", "144p"),
    212: ("video", "mp4", "480p"),
    242: ("video", "webm", "240p"),
    243: ("video", "webm", "360p"),
    244: ("video", "webm", "480p"),
    245: ("video", "webm", "480p"),
    246: ("video", "webm", "480p"),
    247: ("video", "webm", "720p"),
    248: ("video", "webm", "1080p"),
    264: ("video", "mp4", "1440p"),
    271: ("video", "webm", "1440p"),
    272: ("video", "webm", "2160p"),
    278: ("video", "webm", "144p"),
    298: ("video", "mp4", "720p"),
    299: ("video", "mp4", "1080p"),
    302: ("video", "webm", "720p"),
    303: ("video", "webm", "1080p"),
    308: ("video", "webm", "1440p"),
    313: ("video", "webm", "2160p"),
    315: ("video", "webm", "2160p"),
    398: ("video", "mp4", "hd720"),  # sometimes mapped differently
    399: ("video", "mp4", "hd1080"),
    # Audio-only
    139: ("audio", "mp4", "low"),
    140: ("audio", "mp4", "medium"),
    141: ("audio", "mp4", "high"),
    249: ("audio", "webm", "low"),
    250: ("audio", "webm", "medium"),
    251: ("audio", "webm", "high"),
    256: ("audio", "mp4", "medium"),
    258: ("audio", "mp4", "high"),
    325: ("audio", "mp4", "low"),
    328: ("audio", "mp4", "high"),
    # Live stream itags
    91: ("video", "mp4", "live-low"),
    92: ("video", "mp4", "live-low"),
    93: ("video", "mp4", "live-mid"),
    94: ("video", "mp4", "live-high"),
    95: ("video", "mp4", "live-high"),
    96: ("video", "mp4", "live-high"),
    120: ("video", "mp4", "live-hd"),
}


@dataclass
class StreamResult:
    """Result of stream extraction."""
    url: str = ""
    quality: str = ""
    container: str = ""
    video_codec: str = ""
    audio_codec: str = ""
    size: int = 0
    title: str = ""
    video_id: str = ""
    itag: int = 0
    mime_type: str = ""
    raw: dict = field(default_factory=dict)

    def __repr__(self):
        parts = [
            f"quality={self.quality}",
            f"container={self.container}",
            f"video={self.video_codec or 'none'}",
            f"audio={self.audio_codec or 'none'}",
        ]
        if self.size:
            parts.append(f"size={self.size}")
        return f"StreamResult({', '.join(parts)})"


def _parse_mime_type(mime: str) -> tuple[str, str]:
    """Parse 'video/webm; codecs=\"vp9\"' -> ('webm', 'vp9')."""
    if not mime:
        return ("unknown", "")
    parts = mime.split(";")
    container = parts[0].split("/")[-1].strip()
    codecs = ""
    for p in parts:
        p = p.strip()
        if p.startswith("codecs"):
            match = re.search(r'"([^"]+)"', p)
            if match:
                codecs = match.group(1)
    return container, codecs


def _quality_rank(quality_str: str) -> int:
    """Get numeric rank for a quality string."""
    q = quality_str.lower()
    is_k = q.endswith("k")
    q = q.replace("p", "").replace("k", "")
    # Handle things like "hd720", "hd1080"
    if q.startswith("hd"):
        q = q[2:]
    if is_k:
        # 4k = 2160p, 2k = 1440p — use lookup table
        return _QUALITY_RANK.get(quality_str.lower(), -1)
    try:
        return int(q)
    except ValueError:
        pass
    return _QUALITY_RANK.get(quality_str.lower(), -1)


def _format_type(fmt: dict) -> str:
    """Determine if a format is video, audio, or both."""
    mime = fmt.get("mimeType", "")
    if not mime:
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "video"


def _is_video_only(fmt: dict) -> bool:
    """Check if a format is video-only (no audio track)."""
    mime = fmt.get("mimeType", "")
    # Video-only formats have high bitrate and specific codecs
    # or are in adaptiveFormats with a matching audio format
    acodec = fmt.get("audioCodec", "")
    return bool(acodec == "none" or (
        fmt.get("type") == "video" and not acodec
    ))


def find_best_stream(formats: list[dict], quality: str | None = None,
                     audio_only: bool = False, is_live: bool = False,
                     itag_content_length: dict | None = None) -> StreamResult:
    """
    Select the best stream from available formats.

    Parameters
    ----------
    formats : list[dict]
        List of format dicts from streamingData.
    quality : str | None
        Target quality string.
    audio_only : bool
        If True, only consider audio formats.
    is_live : bool
        Whether the stream is live (prefer certain itags).

    Returns
    -------
    StreamResult
    """
    if not formats:
        raise ValueError("No formats available")

    # Filter: keep only formats with actual URLs
    valid = [f for f in formats if f.get("url")]
    if not valid:
        raise ValueError("No formats with URLs available")

    # Filter audio-only if requested
    if audio_only:
        audio_fmts = [f for f in valid if _format_type(f) == "audio"]
        if not audio_fmts:
            raise ValueError("No audio-only formats available")
        best = _pick_best(audio_fmts, "audio", quality or "best")
        return _fmt_to_result(best, "audio")

    # For regular video, we prefer formats with both audio and video
    # (muxed), unless the user explicitly wants a specific quality
    # that only exists as video-only.

    if not quality or quality.lower() == "best":
        # Compare ALL formats together, scoring with contentLength bonus.
        # This way, higher-quality formats with known sizes win over
        # low-quality muxed formats without size info.
        all_valid = [f for f in valid if _format_type(f) == "video"]
        best = _pick_best(all_valid, "video", "best",
                          itag_content_length=itag_content_length)
    else:
        # User requested specific quality
        best = _pick_best(valid, "video", quality,
                          itag_content_length=itag_content_length)
    return _fmt_to_result(best, "video")


def _pick_best(formats: list[dict], ftype: str, quality: str,
               itag_content_length: dict | None = None) -> dict:
    """Pick the best format from a list.

    For video: picks lowest height meeting target quality.
    For audio: picks highest/lowest bitrate based on quality level.
    """
    target_rank = _quality_rank(quality) if ftype == "video" else _AUDIO_RANK.get(
        quality.lower(), 999
    )

    # Score each format
    scored = []
    for fmt in formats:
        itag = fmt.get("itag", 0)
        height = fmt.get("height", 0) or 0
        bitrate = fmt.get("bitrate", 0) or 0
        mime, _ = _parse_mime_type(fmt.get("mimeType", ""))

        if ftype == "video":
            quality_rank = height if height else _quality_rank(
                _ITAG_TYPE_MAP.get(itag, ("", "", "360p"))[2]
            )
        else:
            # Use bitrate as quality rank for audio (higher = better quality)
            quality_rank = bitrate

        scored.append((fmt, quality_rank))

    if target_rank >= 9000:  # "best"
        scored.sort(key=lambda x: x[1], reverse=True)
        return _pick_with_bonus(scored, itag_content_length)
    elif ftype == "audio" and target_rank < 9000:
        # Audio: pick by quality level
        sorted_by_bitrate = sorted(scored, key=lambda x: x[1], reverse=True)
        count = len(sorted_by_bitrate)
        if target_rank >= 800:  # high/best
            return _pick_with_bonus(sorted_by_bitrate[:1], itag_content_length)
        elif target_rank >= 200:  # medium
            # Pick the middle quality format (not highest)
            mid = count // 2
            candidates = sorted_by_bitrate[mid:mid + 1]
            return _pick_with_bonus(candidates, itag_content_length)
        else:  # low/worst
            return _pick_with_bonus(sorted_by_bitrate[-1:], itag_content_length)
    else:
        # Video: prefer formats at or above target
        at_or_above = [(f, q) for f, q in scored if q >= target_rank]
        if at_or_above:
            # Sort ascending by quality, so lowest meeting target is first
            at_or_above.sort(key=lambda x: x[1])
            return _pick_lowest_at_target(at_or_above, itag_content_length)
        else:
            # Nothing meets target, use closest below
            scored.sort(key=lambda x: x[1], reverse=True)
            return _pick_with_bonus(scored, itag_content_length)


def _pick_lowest_at_target(candidates: list[tuple[dict, int]],
                           itag_content_length: dict | None = None,
                           reverse: bool = False) -> dict:
    """Pick the format closest to the target quality.

    For video (reverse=False): picks lowest height meeting target.
    For audio (reverse=True): picks highest bitrate.
    Bonuses (mp4 container, known contentLength) are tiebreakers.
    """
    scored = []
    for fmt, quality_rank in candidates:
        itag = fmt.get("itag", 0)
        mime, _ = _parse_mime_type(fmt.get("mimeType", ""))
        container_bonus = 10 if mime == "mp4" else 0
        cl_bonus = 500 if (itag_content_length and itag in itag_content_length) else 0
        # Primary: quality_rank sorted per reverse
        # Secondary: bonus descending (prefer mp4, prefer known size)
        score = (quality_rank, -(container_bonus + cl_bonus))
        scored.append((score, fmt))

    scored.sort(key=lambda x: x[0], reverse=reverse)
    return scored[0][1]


def _pick_with_bonus(candidates: list[tuple[dict, int]],
                     itag_content_length: dict | None = None) -> dict:
    """From candidate formats, apply container/contentLength bonuses and pick best.

    For video: primary sort by height, bonuses as tiebreakers.
    For audio: primary sort by bitrate (height is always 0 for audio).
    """
    scored = []
    for fmt, _ in candidates:
        itag = fmt.get("itag", 0)
        mime, _ = _parse_mime_type(fmt.get("mimeType", ""))
        container_bonus = 10 if mime == "mp4" else 0
        cl_bonus = 500 if (itag_content_length and itag in itag_content_length) else 0
        # Use height for video, bitrate for audio
        height = fmt.get("height", 0) or 0
        bitrate = fmt.get("bitrate", 0) or 0
        primary = bitrate if height == 0 else height
        score = (primary, container_bonus + cl_bonus)
        scored.append((score, fmt))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _fmt_to_result(fmt: dict, ftype: str) -> StreamResult:
    """Convert a format dict to a StreamResult."""
    mime, codecs = _parse_mime_type(fmt.get("mimeType", ""))
    itag = fmt.get("itag", 0)

    # Split codecs into video and audio
    vcodec = ""
    acodec = ""
    if codecs:
        parts = [c.strip() for c in codecs.split(",")]
        for p in parts:
            if p.startswith("avc") or p.startswith("vp") or p.startswith("av01"):
                vcodec = p
            elif p.startswith("mp4a") or p.startswith("opus"):
                acodec = p

    if ftype == "audio":
        height = 0
        # Use itag-based quality label, not YouTube's internal audioQuality field
        # (YouTube labels high-bitrate opus as AUDIO_QUALITY_MEDIUM)
        itag = fmt.get("itag", 0)
        mapped = _ITAG_TYPE_MAP.get(itag)
        if mapped and mapped[0] == "audio":
            quality_str = mapped[2]  # "high", "medium", or "low"
        else:
            quality_str = fmt.get("audioQuality", "")
            if "medium" in quality_str.lower():
                quality_str = "medium"
            elif "high" in quality_str.lower():
                quality_str = "high"
            else:
                quality_str = mime
        acodec = vcodec if not acodec else acodec
        vcodec = ""
    else:
        height = fmt.get("height", 0) or 0
        quality_str = f"{height}p" if height else fmt.get("qualityLabel", mime)
        # If it's video-only, clear the audio codec
        if _is_video_only(fmt):
            acodec = ""

    return StreamResult(
        url=fmt.get("url", ""),
        quality=quality_str,
        container=mime,
        video_codec=vcodec,
        audio_codec=acodec,
        itag=itag,
        mime_type=fmt.get("mimeType", ""),
        size=fmt.get("contentLength", 0),
        raw=fmt,
    )


def verify_stream(url: str, cookies_file: str | None = None,
                   proxy: str | None = None, timeout: int = 30) -> int:
    """
    Verify a stream URL is accessible by sending a HEAD request
    with a Range header. Returns the content length, or 0 if
    the URL is not accessible.

    Tries up to 3 times with different Range headers to be sure.
    """
    import http.cookiejar
    import urllib.request

    # Build opener
    handlers = []
    if cookies_file:
        cj = http.cookiejar.MozillaCookieJar()
        cj.load(cookies_file, ignore_discard=True, ignore_expires=True)
        handlers.append(urllib.request.HTTPCookieProcessor(cj))
    if proxy:
        handlers.append(urllib.request.ProxyHandler(
            {'http': proxy, 'https': proxy}
        ))
    opener = urllib.request.build_opener(*handlers)

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        ),
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        # YouTube stream URLs require a Referer from youtube.com
        'Referer': 'https://www.youtube.com/',
        'Origin': 'https://www.youtube.com',
    }

    for attempt in range(3):
        try:
            req = Request(url, headers={
                **headers,
                'Range': f'bytes=0-{attempt * 1024}',
            })
            resp = opener.open(req, timeout=timeout)
            code = resp.getcode()
            resp_headers = resp.info()
            content_length = int(resp_headers.get('Content-Length', 0))
            resp.close()
            if content_length > 0:
                return content_length
            # If we got a partial content response, fetch without range
            if code == 206:
                return _verify_no_range(url, handlers, timeout)
        except (HTTPError, URLError, Exception):
            if attempt == 2:
                return 0
            continue

    # Final attempt: full GET to check bytes
    try:
        return _verify_no_range(url, handlers, timeout)
    except Exception:
        return 0


def _verify_no_range(url, handlers, timeout):
    """Verify stream by fetching without Range header, returns bytes."""
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        ),
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.youtube.com/',
        'Origin': 'https://www.youtube.com',
        'Connection': 'keep-alive',
    }
    opener = urllib.request.build_opener(*handlers)
    req = Request(url, headers=headers)
    resp = opener.open(req, timeout=timeout)
    data = resp.read()
    resp.close()
    return len(data)
