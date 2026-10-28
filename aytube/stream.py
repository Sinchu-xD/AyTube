"""
aytube.stream - Stream selection, itag mapping, resolution sorting, and verification.
"""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .utils import build_opener

# Resolution hierarchy
_QUALITY_RANK = {
    "4320p": 4320, "8k": 4320,
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

_AUDIO_RANK = {
    "high": 999,
    "best": 999,
    "medium": 500,
    "low": 100,
    "worst": -1,
}

# Standard YouTube itag specifications
_ITAG_TYPE_MAP: dict[int, tuple[str, str, str]] = {
    # Muxed (Video + Audio)
    18: ("video", "mp4", "360p"),
    22: ("video", "mp4", "720p"),
    34: ("video", "flv", "360p"),
    35: ("video", "flv", "480p"),
    37: ("video", "mp4", "1080p"),
    38: ("video", "mp4", "3072p"),
    # Video only (Adaptive)
    133: ("video", "mp4", "240p"),
    134: ("video", "mp4", "360p"),
    135: ("video", "mp4", "480p"),
    136: ("video", "mp4", "720p"),
    137: ("video", "mp4", "1080p"),
    160: ("video", "mp4", "144p"),
    242: ("video", "webm", "240p"),
    243: ("video", "webm", "360p"),
    244: ("video", "webm", "480p"),
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
    398: ("video", "mp4", "720p"),
    399: ("video", "mp4", "1080p"),
    400: ("video", "mp4", "1440p"),
    401: ("video", "mp4", "2160p"),
    # Audio only (Adaptive)
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
}


@dataclass
class StreamResult:
    """Represents an extracted direct media stream URL with metadata."""
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

    def __str__(self) -> str:
        return self.url

    def __repr__(self) -> str:
        parts = [
            f"url='{self.url[:45]}...'" if len(self.url) > 45 else f"url='{self.url}'",
            f"quality='{self.quality}'",
            f"container='{self.container}'",
            f"itag={self.itag}",
        ]
        if self.video_codec:
            parts.append(f"vcodec='{self.video_codec}'")
        if self.audio_codec:
            parts.append(f"acodec='{self.audio_codec}'")
        if self.size:
            parts.append(f"size={self.size}")
        return f"StreamResult({', '.join(parts)})"


def parse_mime_type(mime: str) -> tuple[str, str]:
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


def codec_from_mime(codecs: str, kind: str) -> str:
    """Extract either video or audio codec from the MIME codecs attribute."""
    if not codecs:
        return ""
    parts = [c.strip() for c in codecs.split(",")]
    for p in parts:
        if kind == "video" and (p.startswith("avc") or p.startswith("vp") or p.startswith("av01")):
            return p
        if kind == "audio" and (p.startswith("mp4a") or p.startswith("opus")):
            return p
    return ""


def format_type(fmt: dict) -> str:
    """Determine whether a format is video or audio."""
    mime = fmt.get("mimeType", "")
    if mime.startswith("audio/"):
        return "audio"
    return "video"


def is_video_only(fmt: dict) -> bool:
    """Check if a format is video-only without an embedded audio channel."""
    mime = fmt.get("mimeType", "")
    acodec = fmt.get("audioCodec", "")
    if acodec == "none":
        return True
    if mime.startswith("video/") and not acodec:
        container, codecs = parse_mime_type(mime)
        return not bool(codec_from_mime(codecs, "audio"))
    return False


def quality_rank(quality_str: str) -> int:
    """Calculate a numeric rank for sorting resolutions."""
    q = str(quality_str).lower().replace("p", "").replace("k", "")
    if q.startswith("hd"):
        q = q[2:]
    if str(quality_str).lower().endswith("k"):
        return _QUALITY_RANK.get(quality_str.lower(), -1)
    try:
        return int(q)
    except ValueError:
        pass
    return _QUALITY_RANK.get(quality_str.lower(), -1)


def find_best_stream(
    formats: list[dict],
    quality: str | None = None,
    audio_only: bool = False,
    is_live: bool = False,
    itag_content_length: dict | None = None,
) -> StreamResult:
    """
    Select the best stream matching criteria from available formats.
    """
    if not formats:
        raise ValueError("No stream formats available.")

    valid = [f for f in formats if f.get("url")]
    if not valid:
        raise ValueError("No formats with direct URLs available.")

    if audio_only:
        audio_fmts = [f for f in valid if format_type(f) == "audio"]
        if not audio_fmts:
            raise ValueError("No audio-only formats available.")
        best = _pick_best(audio_fmts, "audio", quality or "best", itag_content_length)
        return _fmt_to_result(best, "audio")

    if not quality or quality.lower() == "best":
        video_fmts = [f for f in valid if format_type(f) == "video"]
        if not video_fmts:
            video_fmts = valid
        best = _pick_best(video_fmts, "video", "best", itag_content_length)
    else:
        try:
            target_itag = int(quality)
            matches = [f for f in valid if f.get("itag") == target_itag]
            if matches:
                best = _pick_best(matches, "video", "best", itag_content_length)
            else:
                best = _pick_best(valid, "video", quality, itag_content_length)
        except ValueError:
            best = _pick_best(valid, "video", quality, itag_content_length)

    return _fmt_to_result(best, "video")


def _pick_best(
    formats: list[dict],
    ftype: str,
    target_quality: str,
    itag_content_length: dict | None = None,
) -> dict:
    target_rank = quality_rank(target_quality) if ftype == "video" else _AUDIO_RANK.get(
        target_quality.lower(), 999
    )

    scored: list[tuple[dict, int]] = []
    for fmt in formats:
        itag = fmt.get("itag", 0)
        height = fmt.get("height", 0) or 0
        bitrate = fmt.get("bitrate", 0) or 0

        if ftype == "video":
            q_rank = height if height else quality_rank(
                _ITAG_TYPE_MAP.get(itag, ("", "", "360p"))[2]
            )
        else:
            q_rank = bitrate
        scored.append((fmt, q_rank))

    if target_rank >= 9000:
        scored.sort(key=lambda x: x[1], reverse=True)
        return _pick_with_bonus(scored, itag_content_length)

    if ftype == "audio":
        sorted_by_bitrate = sorted(scored, key=lambda x: x[1], reverse=True)
        if target_rank >= 800:
            return _pick_with_bonus(sorted_by_bitrate[:1], itag_content_length)
        if target_rank >= 200:
            medium_matches = [
                (f, q) for f, q in sorted_by_bitrate
                if _ITAG_TYPE_MAP.get(f.get("itag", 0), ("", "", ""))[2] == "medium"
            ]
            if medium_matches:
                return _pick_with_bonus(medium_matches, itag_content_length)
            mid = max(0, (len(sorted_by_bitrate) - 1) // 2)
            return _pick_with_bonus(sorted_by_bitrate[mid:mid + 1], itag_content_length)
        return _pick_with_bonus(sorted_by_bitrate[-1:], itag_content_length)

    # Video: target specific resolution
    at_or_above = [(f, q) for f, q in scored if q >= target_rank]
    if at_or_above:
        at_or_above.sort(key=lambda x: x[1])
        return _pick_lowest_at_target(at_or_above, itag_content_length)

    scored.sort(key=lambda x: x[1], reverse=True)
    return _pick_with_bonus(scored, itag_content_length)


def _pick_lowest_at_target(
    candidates: list[tuple[dict, int]],
    itag_content_length: dict | None = None,
) -> dict:
    scored = []
    for fmt, rank in candidates:
        itag = fmt.get("itag", 0)
        mime, _ = parse_mime_type(fmt.get("mimeType", ""))
        container_bonus = 10 if mime == "mp4" else 0
        cl_bonus = 500 if (itag_content_length and itag in itag_content_length) else 0
        score = (rank, -(container_bonus + cl_bonus))
        scored.append((score, fmt))
    scored.sort(key=lambda x: x[0])
    return scored[0][1]


def _pick_with_bonus(
    candidates: list[tuple[dict, int]],
    itag_content_length: dict | None = None,
) -> dict:
    scored = []
    for fmt, _ in candidates:
        itag = fmt.get("itag", 0)
        mime, _ = parse_mime_type(fmt.get("mimeType", ""))
        container_bonus = 10 if mime == "mp4" else 0
        cl_bonus = 500 if (itag_content_length and itag in itag_content_length) else 0
        height = fmt.get("height", 0) or 0
        bitrate = fmt.get("bitrate", 0) or 0
        primary = bitrate if height == 0 else height
        score = (primary, container_bonus + cl_bonus)
        scored.append((score, fmt))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _fmt_to_result(fmt: dict, ftype: str) -> StreamResult:
    mime, codecs = parse_mime_type(fmt.get("mimeType", ""))
    itag = fmt.get("itag", 0)

    vcodec = codec_from_mime(codecs, "video")
    acodec = codec_from_mime(codecs, "audio")

    if ftype == "audio":
        mapped = _ITAG_TYPE_MAP.get(itag)
        if mapped and mapped[0] == "audio":
            quality_str = mapped[2]
        else:
            q_label = fmt.get("audioQuality", "")
            if "medium" in q_label.lower():
                quality_str = "medium"
            elif "high" in q_label.lower():
                quality_str = "high"
            else:
                quality_str = "low"
        acodec = acodec or vcodec
        vcodec = ""
    else:
        height = fmt.get("height", 0) or 0
        quality_str = f"{height}p" if height else fmt.get("qualityLabel", mime)
        if is_video_only(fmt):
            acodec = ""

    content_len = int(fmt.get("contentLength", 0) or 0)

    return StreamResult(
        url=fmt.get("url", ""),
        quality=quality_str,
        container=mime,
        video_codec=vcodec,
        audio_codec=acodec,
        itag=itag,
        mime_type=fmt.get("mimeType", ""),
        size=content_len,
        raw=fmt,
    )


def verify_stream(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 15,
) -> int:
    """
    Verify stream playability via HTTP byte-range request. Returns content length or 0.
    """
    opener = build_opener(cookies_file, proxy)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Referer": "https://www.youtube.com/",
        "Origin": "https://www.youtube.com",
        "Range": "bytes=0-1024",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = opener.open(req, timeout=timeout)
        code = resp.getcode()
        resp_headers = resp.info()
        resp.close()
        if code in (200, 206):
            cr = resp_headers.get("Content-Range", "")
            if "/" in cr:
                try:
                    return int(cr.split("/")[-1])
                except ValueError:
                    pass
            return int(resp_headers.get("Content-Length", 0))
    except Exception:
        pass
    return 0
