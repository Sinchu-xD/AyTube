"""
aytube - Extract direct YouTube stream URLs from ANY YouTube URL format.

Primary method: HTML scraping (proven, no dependencies)
Optional: innertube API with PoToken support
"""

__version__ = "2.0.0"
__author__ = "ABHISHEK THAKUR"
__email__ = "abhiyanshicreation@gmail.com"

import json
import re
import sys
import time
from urllib.parse import parse_qs, unquote
from urllib.error import HTTPError

from .url import extract_video_id
from .fetcher import fetch_page, fetch_player_js, extract_player_js_url
from .player import get_player_response
from .cipher import extract_cipher_function, extract_n_function, decipher, decipher_n, extract_key
from .stream import find_best_stream, verify_stream, StreamResult, _parse_mime_type, _ITAG_TYPE_MAP

from .batch import batch_download
from .age import bypass_age_check
try:
    from .potoken import generate_po_token
except ImportError:
    def generate_po_token(*args, **kwargs):
        return ""
from .search import search
from .thumbnail import get_thumbnails, download_thumbnail
from .chapters import get_chapters
from .related import get_related_videos
from .channel_info import get_channel_info, get_channel_avatar
from .config import load_config, save_config, get_config, set_config, setup_wizard, show_config
from .resume import download_with_resume, get_file_size

__all__ = [
    "extract_video_id",
    "get_stream_url",
    "list_formats",
    "get_metadata",
    "download",
    "download_with_resume",
    "list_playlist",
    "list_subtitles",
    "batch_download",
    "bypass_age_check",
    "generate_po_token",
    "search",
    "get_thumbnails",
    "download_thumbnail",
    "get_chapters",
    "get_related_videos",
    "get_channel_info",
    "get_channel_avatar",
    "load_config",
    "save_config",
    "get_config",
    "set_config",
    "setup_wizard",
    "show_config",
    "StreamResult",
]


# ─── Helpers ───────────────────────────────────────────────────────────────

def _decode_signature_cipher(cipher_str: str) -> dict:
    """Decode a YouTube 'signatureCipher' field."""
    decoded = unquote(cipher_str)
    params = parse_qs(decoded)
    return {key: (params[key][0] if params.get(key) else "") for key in ('s', 'sp', 'url', 'n')}


def _resolve_signature_format(fmt: dict) -> str:
    """Extract a playable URL from a format dict (modern or legacy)."""
    if fmt.get("signatureCipher"):
        parts = _decode_signature_cipher(fmt["signatureCipher"])
        base_url = parts.get("url", "")
        sp = parts.get("sp", "signature")
        sig = parts.get("s", "")
        if base_url and sig:
            sep = "&" if "?" in base_url else "?"
            return f"{base_url}{sep}{sp}={sig}"
        return base_url

    if fmt.get("url"):
        url_str = fmt["url"]
        sig = fmt.get("s", "")
        sp = fmt.get("sp", "signature")
        if sig:
            sep = "&" if "?" in url_str else "?"
            url_str = f"{url_str}{sep}{sp}={sig}"
        return url_str
    return ""


def _has_cipher(all_formats: list) -> bool:
    return any(fmt.get("signatureCipher") or fmt.get("s") for fmt in all_formats)


def _has_n_parameter(all_formats: list) -> bool:
    for fmt in all_formats:
        cipher = fmt.get("signatureCipher", "")
        if "&n=" in cipher or fmt.get("n"):
            return True
    return False


def _apply_n_parameter(url: str, n_value: str, n_func) -> str:
    if not n_value or not n_func:
        return url
    try:
        transformed = decipher_n(n_func, n_value)
        if transformed and transformed != n_value:
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}n={transformed}"
    except Exception:
        pass
    return url


def _build_format_url(base_url: str, sig_value: str, sig_param_name: str, fmt: dict) -> str:
    """Build stream URL for adaptive format. Replace itag and append signature."""
    target_itag = fmt.get("itag", 0)
    if not target_itag or "?" not in base_url:
        return ""

    prefix, query = base_url.split("?", 1)

    # Extract existing itag from base_url (from muxed format signatureCipher)
    existing_itag = ""
    for param in query.split("&"):
        if param.startswith("itag="):
            existing_itag = param.split("=", 1)[1]
            break

    # Rebuild query params: replace itag, update sparams
    param_dict = {}
    itag_done = False

    for param in query.split("&"):
        if "=" not in param:
            continue
        key, _, val = param.partition("=")
        if key == "itag":
            if not itag_done:
                param_dict["itag"] = str(target_itag)
                itag_done = True
        elif key == "sparams" and existing_itag:
            # Replace old itag with new in sparams list
            sp_items = val.split(",")
            sp_items = [str(target_itag) if p == existing_itag else p for p in sp_items]
            param_dict["sparams"] = ",".join(sp_items)
        else:
            param_dict[key] = val

    # Append deciphered signature
    if sig_value:
        param_dict[sig_param_name] = sig_value

    return f"{prefix}?{'&'.join(f'{k}={v}' for k, v in param_dict.items())}"


def _is_rate_limited(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in (429, 403, 503)
    return False


def _find_cookies_path(cookies_file: str | None) -> str | None:
    if cookies_file:
        return cookies_file
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "cookies_file"),
        os.path.join(os.getcwd(), "cookies_file"),
        os.path.expanduser("~/.config/aytube/cookies_file"),
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if os.path.isfile(path):
            return path
    return None


def _detect_bot_challenge(html: str) -> bool:
    """Detect if YouTube returned a bot verification page."""
    return ("Sign in to confirm you're not a bot" in html or
            'id="captcha"' in html or '/Captcha' in html)


# ─── HTML scraping (primary method) ──────────────────────────────────────

def _process_formats_html(all_formats, html, cookies, proxy, timeout):
    """Process formats using HTML scraping with cipher decryption."""
    needs_cipher = _has_cipher(all_formats)
    needs_n = _has_n_parameter(all_formats)
    n_func = None

    if needs_cipher or needs_n:
        html_key = extract_key(js=None, html=html)
        if html_key:
            needs_cipher = True

        try:
            player_js_url = extract_player_js_url(html)
        except RuntimeError:
            player_js_url = None

        js_code = None
        if player_js_url:
            try:
                js_code = fetch_player_js(player_js_url, cookies_file=cookies,
                                          proxy=proxy, timeout=timeout)
            except Exception:
                pass

        if needs_cipher and js_code:
            cipher_func = extract_cipher_function(js_code, aes_key=html_key or None)
            if cipher_func is None:
                raise RuntimeError("Could not extract cipher function from player JS.")

            _sig_base_url = ""
            _sig_deciphered = ""
            _sig_sp = "signature"
            cipher_count = 0

            for fmt in all_formats:
                sig_info = _decode_signature_cipher(
                    fmt.pop("signatureCipher", "")
                ) if fmt.get("signatureCipher") else {
                    "s": fmt.pop("s", ""),
                    "sp": fmt.get("sp", "signature"),
                    "url": fmt.get("url", ""),
                }

                sig = sig_info.get("s", "")
                if sig:
                    cipher_count += 1
                    try:
                        deciphered = decipher(cipher_func, sig)
                        sp = sig_info.get("sp", "signature")
                        base_url = sig_info.get("url", "")
                        if base_url:
                            sep = "&" if "?" in base_url else "?"
                            fmt["url"] = f"{base_url}{sep}{sp}={deciphered}"
                        elif fmt.get("url"):
                            sep = "&" if "?" in fmt["url"] else "?"
                            fmt["url"] = f"{fmt['url']}{sep}{sp}={deciphered}"
                        if not _sig_base_url and base_url:
                            _sig_base_url = base_url
                            _sig_deciphered = deciphered
                            _sig_sp = sp
                    except RuntimeError:
                        pass

                fmt.pop("sp", None)
                fmt.pop("s", None)

            # Build URLs for adaptive formats that lack them
            if _sig_base_url and _sig_deciphered:
                for fmt in all_formats:
                    if not fmt.get("url"):
                        fmt["url"] = _build_format_url(
                            _sig_base_url, _sig_deciphered, _sig_sp, fmt
                        )

        if needs_n and js_code:
            n_func = extract_n_function(js_code)

    # Resolve remaining URLs
    resolved = 0
    for fmt in all_formats:
        if not fmt.get("url"):
            fmt["url"] = _resolve_signature_format(fmt)
            if fmt.get("url"):
                resolved += 1

    return all_formats, n_func


# ─── Innertube API (optional, needs PoToken) ──────────────────────────────

def _process_formats_innertube(all_formats, n_func=None):
    """Process formats from innertube API (URLs are pre-signed)."""
    for fmt in all_formats:
        fmt.pop("sp", None)
        fmt.pop("s", None)
        if not fmt.get("url"):
            fmt["url"] = _resolve_signature_format(fmt)
    return all_formats, n_func


# ─── Main entry point ─────────────────────────────────────────────────────

def get_stream_url(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    quality: str | None = None,
    audio_only: bool = False,
    verify: bool = True,
    timeout: int = 30,
    method: str = "html",
) -> StreamResult:
    """
    Extract a playable stream URL from a YouTube video.

    Parameters
    ----------
    url : str
        A YouTube URL (watch, shorts, embed, youtu.be).
    cookies_file : str | None
        Path to a Netscape-format cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    quality : str | None
        Preferred quality: "1080p", "720p", "480p", "360p", "best", "worst".
    audio_only : bool
        If True, return an audio-only stream.
    verify : bool
        If True, verify the stream URL is reachable.
    timeout : int
        Request timeout in seconds.
    method : str
        "html" (default) — proven working, no dependencies.
        "innertube" — YouTube API (requires PoToken, experimental).
        "auto" — try HTML first, fallback to innertube.

    Returns
    -------
    StreamResult
        Object with .url, .quality, .container, .video_codec, .audio_codec,
        .size, .title, .video_id.
    """
    import os

    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    use_html = method in ("auto", "html")
    use_innertube = method in ("auto", "innertube")
    if method == "html":
        use_innertube = False
    elif method == "innertube":
        use_html = False

    # ── Fetch data ──
    player_response = None
    html = None
    n_func = None
    fetch_method = None

    # Primary: HTML scraping
    if use_html:
        cookies = cookies_file
        last_exc = None
        for attempt in range(2):
            try:
                html = fetch_page(video_id, cookies_file=cookies,
                                  proxy=proxy, timeout=timeout)

                # Check for bot challenge
                if _detect_bot_challenge(html):
                    if attempt == 0 and not cookies_file:
                        cookies = _find_cookies_path(cookies_file)
                        if cookies:
                            time.sleep(2)
                            continue
                    raise RuntimeError(
                        "YouTube returned a bot verification page. "
                        "Try providing a cookies_file with an authenticated session."
                    )

                player_response = get_player_response(html)
                fetch_method = "html"
                break
            except Exception as exc:
                last_exc = exc
                if _is_rate_limited(exc) and attempt == 0 and not cookies_file:
                    cookies = _find_cookies_path(cookies_file)
                    if cookies:
                        time.sleep(2)
                        continue
                raise

        if not player_response:
            raise last_exc or RuntimeError("Failed to fetch page")

    # Fallback: innertube API
    if not player_response and use_innertube:
        try:
            from .innertube import fetch_player_response
            resp = fetch_player_response(
                video_id,
                cookies_file=cookies_file,
                proxy=proxy,
                timeout=timeout,
            )
            player_response = resp
            fetch_method = "innertube"
        except Exception:
            player_response = None

    if not player_response:
        raise RuntimeError("Could not fetch player response via any method")

    # ── Extract streaming data ──
    streaming_data = player_response.get("streamingData", {})
    video_details = player_response.get("videoDetails", {})
    playability = player_response.get("playabilityStatus", {})

    title = video_details.get("title", "")
    is_live = video_details.get("isLive", False)

    formats = streaming_data.get("formats", [])
    adaptive_formats = streaming_data.get("adaptiveFormats", [])
    all_formats = [dict(f) for f in formats] + [dict(f) for f in adaptive_formats]

    if not all_formats:
        status = playability.get("status", "")
        reason = playability.get("reason", "Unknown reason")
        if status in ("AGE_CHECK_REQUIRED", "AGE_VERIFICATION_REQUIRED"):
            raise ValueError("Age-restricted video. Provide a cookies_file.")
        if status == "LIVE_STREAM_OFFLINE":
            raise ValueError("This live stream is currently offline.")
        if status == "UNPLAYABLE":
            raise ValueError(f"Video is unplayable: {reason or 'region or format restrictions'}")
        raise ValueError(f"Cannot play this video: {reason}")

    # ── Build contentLength map ──
    _itag_content_length = {}
    for fmt in all_formats:
        itag = fmt.get("itag")
        cl = fmt.get("contentLength")
        if itag and cl:
            _itag_content_length[itag] = int(cl)

    # ── Resolve URLs ──
    if fetch_method == "innertube":
        all_formats, n_func = _process_formats_innertube(all_formats)
    else:
        all_formats, n_func = _process_formats_html(
            all_formats, html, cookies_file, proxy, timeout
        )

    # ── Select best stream ──
    result = find_best_stream(
        all_formats,
        quality=quality,
        audio_only=audio_only,
        is_live=is_live,
        itag_content_length=_itag_content_length,
    )

    result.title = title
    result.video_id = video_id

    # ── Apply n-parameter ──
    if result.url and n_func:
        for fmt in all_formats:
            cipher = fmt.get("signatureCipher", "")
            if "&n=" in cipher:
                n_match = _decode_signature_cipher(cipher)
                n_value = n_match.get("n", "")
                if n_value:
                    result.url = _apply_n_parameter(result.url, n_value, n_func)
                    break

    # ── Verify stream ──
    if verify and result.url:
        if result.itag and result.itag in _itag_content_length:
            result.size = _itag_content_length[result.itag]
        if result.size == 0:
            file_size = verify_stream(result.url, cookies_file=cookies_file,
                                       proxy=proxy, timeout=timeout)
            result.size = file_size

    # If using HTML method and Innertube is available, always try Innertube
    # as a fallback (HTML-built URLs often fail with 403 from CDN)
    if fetch_method == "html" and use_innertube:
        try:
            from .innertube import fetch_player_response
            resp2 = fetch_player_response(video_id, cookies_file=cookies_file,
                                          proxy=proxy, timeout=timeout)
            sd2 = resp2.get("streamingData", {})
            fmts2 = sd2.get("formats", []) + sd2.get("adaptiveFormats", [])
            innertube_result = find_best_stream(fmts2, quality=quality,
                                                 audio_only=audio_only, is_live=is_live)
            if innertube_result.url:
                result.url = innertube_result.url
                result.itag = innertube_result.itag
                result.quality = innertube_result.quality
                result.video_codec = innertube_result.video_codec
                result.audio_codec = innertube_result.audio_codec
                result.container = innertube_result.container
                result.size = innertube_result.size or result.size
                fetch_method = "innertube"
        except Exception:
            pass

    return result


# ─── Public API: list_formats ─────────────────────────────────────────────

def list_formats(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    audio_only: bool = False,
    timeout: int = 30,
) -> list[dict]:
    """
    List all available stream formats for a YouTube video.

    Parameters
    ----------
    url : str
        YouTube video URL.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    audio_only : bool
        If True, only list audio formats.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    list[dict]
        Each dict has: itag, quality, container, video_codec, audio_codec,
        size, bitrate, fps, mime_type, is_hdr, is_video_only.
    """
    import os
    from .fetcher import fetch_page
    from .player import get_player_response

    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    # Fetch page
    html = fetch_page(video_id, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
    pr = get_player_response(html)
    sd = pr.get("streamingData", {})

    formats = sd.get("formats", []) + sd.get("adaptiveFormats", [])

    # Resolve URLs
    needs_cipher = any(f.get("signatureCipher") or f.get("s") for f in formats)
    needs_n = any("&n=" in f.get("signatureCipher", "") or f.get("n") for f in formats)
    n_func = None

    if needs_cipher or needs_n:
        from .cipher import extract_key, extract_cipher_function, extract_n_function
        from .fetcher import extract_player_js_url, fetch_player_js

        html_key = extract_key(js=None, html=html)
        try:
            player_js_url = extract_player_js_url(html)
        except RuntimeError:
            player_js_url = None

        js_code = None
        if player_js_url:
            try:
                js_code = fetch_player_js(player_js_url, cookies_file=cookies_file,
                                          proxy=proxy, timeout=timeout)
            except Exception:
                pass

        if needs_cipher and js_code:
            cipher_func = extract_cipher_function(js_code, aes_key=html_key or None)

            _sig_base_url = _sig_deciphered = _sig_sp = ""
            for fmt in formats:
                sig_info = _decode_signature_cipher(fmt.pop("signatureCipher", "")) if fmt.get("signatureCipher") else {
                    "s": fmt.pop("s", ""), "sp": fmt.get("sp", "signature"), "url": fmt.get("url", ""),
                }
                sig = sig_info.get("s", "")
                if sig and cipher_func:
                    try:
                        deciphered = decipher(cipher_func, sig)
                        sp = sig_info.get("sp", "signature")
                        base_url = sig_info.get("url", "")
                        if base_url:
                            sep = "&" if "?" in base_url else "?"
                            fmt["url"] = f"{base_url}{sep}{sp}={deciphered}"
                        elif fmt.get("url"):
                            sep = "&" if "?" in fmt["url"] else "?"
                            fmt["url"] = f"{fmt['url']}{sep}{sp}={deciphered}"
                        if not _sig_base_url and base_url:
                            _sig_base_url = base_url
                            _sig_deciphered = deciphered
                            _sig_sp = sp
                    except RuntimeError:
                        pass
                fmt.pop("sp", None)
                fmt.pop("s", None)

            if _sig_base_url and _sig_deciphered:
                for fmt in formats:
                    if not fmt.get("url"):
                        fmt["url"] = _build_format_url(_sig_base_url, _sig_deciphered, _sig_sp, fmt)

        if needs_n and js_code:
            n_func = extract_n_function(js_code)

    # Resolve remaining URLs
    for fmt in formats:
        if not fmt.get("url"):
            fmt["url"] = _resolve_signature_format(fmt)

    # Apply n-parameter
    if n_func:
        for fmt in formats:
            cipher = fmt.get("signatureCipher", "")
            if "&n=" in cipher:
                n_match = _decode_signature_cipher(cipher)
                n_value = n_match.get("n", "")
                if n_value:
                    fmt["url"] = _apply_n_parameter(fmt["url"], n_value, n_func)

    # Build format list
    result = []
    for fmt in formats:
        mime, codecs = _parse_mime_type(fmt.get("mimeType", ""))
        itag = fmt.get("itag", 0)
        height = fmt.get("height", 0) or 0
        ftype = "audio" if fmt.get("mimeType", "").startswith("audio") else "video"

        if audio_only and ftype != "audio":
            continue

        size = int(fmt.get("contentLength", 0) or 0)
        bitrate = fmt.get("bitrate", 0) or 0
        fps = fmt.get("fps", 0) or 0

        # Quality label
        if ftype == "audio":
            mapped = _ITAG_TYPE_MAP.get(itag)
            if mapped and mapped[0] == "audio":
                quality_label = mapped[2]
            else:
                aq = fmt.get("audioQuality", "")
                quality_label = "high" if "high" in aq.lower() else "medium" if "medium" in aq.lower() else "low"
        else:
            quality_label = f"{height}p" if height else fmt.get("qualityLabel", "")

        # HDR detection
        is_hdr = any(hdr in (codecs or "").lower() for hdr in ["hdr", "bt2020", "smpte2084"])

        # Video-only detection
        is_video_only = fmt.get("audioCodec") == "none" or (
            ftype == "video" and not fmt.get("audioCodec")
        )

        result.append({
            "itag": itag,
            "quality": quality_label,
            "container": mime,
            "video_codec": _codec_from_mime(codecs, "video") or fmt.get("video_codec") or fmt.get("videoCodec", ""),
            "audio_codec": _codec_from_mime(codecs, "audio") or fmt.get("audio_codec") or fmt.get("audioCodec", ""),
            "mime_type": fmt.get("mimeType", ""),
            "size": size,
            "bitrate": bitrate,
            "fps": fps,
            "is_hdr": is_hdr,
            "is_video_only": is_video_only,
            "url": fmt.get("url", ""),
            "raw": fmt,
        })

    return result


def _codec_from_mime(codecs: str, kind: str) -> str:
    """Extract video or audio codec from MIME codecs string."""
    if not codecs:
        return ""
    parts = [c.strip() for c in codecs.split(",")]
    video_prefixes = ("avc", "av01", "vp9", "vp8")
    audio_prefixes = ("mp4a", "opus", "vorbis")
    prefixes = video_prefixes if kind == "video" else audio_prefixes
    for p in parts:
        if any(p.startswith(pref) for pref in prefixes):
            return p.split(".")[0]
    return ""


# ─── Public API: get_metadata ─────────────────────────────────────────────

def get_metadata(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict:
    """
    Extract video metadata without downloading.

    Parameters
    ----------
    url : str
        YouTube video URL.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    dict
        title, description, thumbnail, duration, view_count, like_count,
        channel_name, channel_id, upload_date, is_live, is_private, etc.
    """
    import os
    from .fetcher import fetch_page
    from .player import get_player_response

    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    html = fetch_page(video_id, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
    pr = get_player_response(html)

    vd = pr.get("videoDetails", {})
    ps = pr.get("playabilityStatus", {})

    # Duration in seconds
    length_sec = int(vd.get("lengthSeconds", 0) or 0)
    duration = _format_duration(length_sec)

    # Thumbnails
    thumbs = vd.get("thumbnail", {}).get("thumbnails", [])
    thumbnail = thumbs[-1].get("url") if thumbs else ""

    # Upload date
    upload_date = vd.get("uploadDate", "")

    # Live status
    is_live = vd.get("isLive", False)

    # View count
    view_count = int(vd.get("viewCount", 0) or 0)

    # Author info
    author = vd.get("author", "")
    channel_id = vd.get("channelId", "")

    # Description
    description = vd.get("shortDescription", "")

    return {
        "video_id": video_id,
        "title": vd.get("title", ""),
        "description": description,
        "thumbnail": thumbnail,
        "thumbnail_urls": [t.get("url") for t in thumbs],
        "duration": duration,
        "duration_seconds": length_sec,
        "view_count": view_count,
        "like_count": 0,  # Not in standard response
        "channel_name": author,
        "channel_id": channel_id,
        "upload_date": upload_date,
        "is_live": is_live,
        "is_private": vd.get("isPrivate", False),
        "is_unplugged": vd.get("isUnpluggedCorpus", False),
        "playability_status": ps.get("status", ""),
        "playability_reason": ps.get("reason", ""),
        "keywords": vd.get("keywords", []),
        "category": vd.get("category", ""),
        "is_age_restricted": vd.get("isAgeRestricted", False),
    }


def _format_duration(seconds: int) -> str:
    """Format seconds to HH:MM:SS or MM:SS."""
    if not seconds:
        return "0:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ─── Public API: download ──────────────────────────────────────────────────

def download(
    url: str,
    output: str | None = None,
    cookies_file: str | None = None,
    proxy: str | None = None,
    quality: str | None = None,
    audio_only: bool = False,
    mux: bool = False,
    timeout: int = 60,
) -> str:
    """
    Download a YouTube video or audio stream to a file.

    Parameters
    ----------
    url : str
        YouTube video URL.
    output : str | None
        Output file path. If None, uses video title as filename.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    quality : str | None
        Preferred quality.
    audio_only : bool
        If True, download audio only.
    mux : bool
        If True, download both video and audio and merge with ffmpeg.
        Requires ffmpeg installed on the system.
    timeout : int
        Download timeout in seconds.

    Returns
    -------
    str
        Path to the downloaded file.
    """
    import os
    import sys

    result = get_stream_url(
        url,
        cookies_file=cookies_file,
        proxy=proxy,
        quality=quality,
        audio_only=audio_only,
        verify=False,
        timeout=timeout,
        method="html",  # HTML gives working cipher URLs
    )

    if not result.url:
        raise RuntimeError("No stream URL available")

    # Determine output path
    if not output:
        safe_title = _safe_filename(result.title or result.video_id)
        ext = "m4a" if audio_only else result.container or "mp4"
        output = f"{safe_title}.{ext}"

    # Ensure output directory exists
    out_dir = os.path.dirname(output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if mux and not audio_only:
        return _download_and_mux(result, output, cookies_file, proxy, timeout)
    else:
        return _download_file(result.url, output, cookies_file, proxy, timeout,
                              result.size, result.title, resume=True)


def _safe_filename(name: str, max_len: int = 100) -> str:
    """Sanitize a string for use as a filename."""
    import re
    # Remove/replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "download"


def _download_file(url: str, output: str, cookies_file: str | None,
                   proxy: str | None, timeout: int, size: int = 0,
                   title: str = "", resume: bool = True) -> str:
    """Download a file using urllib with cookies, fallback to curl."""
    import os
    import subprocess
    import sys
    import http.cookiejar
    import urllib.request
    import urllib.error

    # Try urllib first (better cookie handling across domains)
    try:
        cj = http.cookiejar.MozillaCookieJar()
        if cookies_file and os.path.exists(cookies_file):
            cj.load(cookies_file, ignore_discard=True, ignore_expires=True)

        proxy_map = {'http': proxy, 'https': proxy} if proxy else {}
        # Build cookie header manually (cross-domain: youtube.com cookies → googlevideo.com)
        cookie_header = "; ".join(
            f"{c.name}={c.value}" for c in cj if c.value
        ) if cookies_file and os.path.exists(cookies_file) else None

        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.ProxyHandler(proxy_map),
        )
        opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
            ('Accept', 'video/webm,video/mp4,video/*;q=0.9,*/*;q=0.8'),
            ('Accept-Language', 'en-US,en;q=0.9'),
            ('Accept-Encoding', 'identity'),
            ('Referer', 'https://www.youtube.com/'),
            ('Origin', 'https://www.youtube.com'),
            ('Sec-Fetch-Dest', 'video'),
            ('Sec-Fetch-Mode', 'no-cors'),
            ('Sec-Fetch-Site', 'cross-site'),
        ]
        if cookie_header:
            opener.addheaders.append(('Cookie', cookie_header))

        mode = 'ab' if (resume and os.path.exists(output) and os.path.getsize(output) > 0) else 'wb'
        headers_dict = {}
        if mode == 'ab':
            downloaded = os.path.getsize(output)
            headers_dict['Range'] = f'bytes={downloaded}-'
            print(f"  Resuming from {downloaded / 1024 / 1024:.1f}MB")

        req = urllib.request.Request(url, headers=headers_dict)
        resp = opener.open(req, timeout=timeout * 4)

        total_size = int(resp.headers.get('Content-Length', 0)) if mode == 'wb' else 0

        with open(output, mode) as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                total_size += len(chunk)
                if total_size > 0:
                    pct = min((total_size / max(total_size, 1)) * 100, 100)
                    mb = total_size / (1024 * 1024)
                    bar_len = 30
                    filled = int(bar_len * min(total_size / max(total_size, 1), 1))
                    bar = "█" * filled + "░" * (bar_len - filled)
                    sys.stdout.write(f"\r  {bar} {pct:5.1f}% {mb:.1f} MB")
                    sys.stdout.flush()

        print()
        if os.path.exists(output) and os.path.getsize(output) > 0:
            return output

    except urllib.error.HTTPError as e:
        if e.code == 403:
            # Retry without proxy, with all cookies as header
            try:
                cj3 = http.cookiejar.MozillaCookieJar()
                if cookies_file and os.path.exists(cookies_file):
                    cj3.load(cookies_file, ignore_discard=True, ignore_expires=True)
                cookie_header3 = "; ".join(
                    f"{c.name}={c.value}" for c in cj3 if c.value
                )
                opener3 = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(cj3),
                )
                opener3.addheaders = [
                    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
                    ('Accept', '*/*'),
                    ('Referer', 'https://www.youtube.com/'),
                    ('Origin', 'https://www.youtube.com'),
                ]
                if cookie_header3:
                    opener3.addheaders.append(('Cookie', cookie_header3))
                resp3 = opener3.open(urllib.request.Request(url), timeout=timeout * 4)
                with open(output, 'wb') as f:
                    while True:
                        chunk = resp3.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                if os.path.exists(output) and os.path.getsize(output) > 0:
                    return output
            except Exception:
                pass
    except Exception:
        pass

    # Fallback: curl
    cmd = [
        "curl", "-L", "-f",
        "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-H", "Accept: video/webm,video/mp4,video/*;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.9",
        "-H", "Accept-Encoding: identity",
        "-H", "Referer: https://www.youtube.com/",
        "-H", "Origin: https://www.youtube.com",
        "-H", "Sec-Fetch-Dest: video",
        "-H", "Sec-Fetch-Mode: no-cors",
        "-H", "Sec-Fetch-Site: cross-site",
        "--connect-timeout", str(timeout),
        "--max-time", str(timeout * 4),
        "-o", output,
        "--progress-bar",
        url,
    ]

    if cookies_file and os.path.exists(cookies_file):
        cmd.extend(["-b", cookies_file])
        try:
            cj2 = http.cookiejar.MozillaCookieJar()
            cj2.load(cookies_file, ignore_discard=True, ignore_expires=True)
            key_cookies = ["LOGIN_INFO", "SID", "HSID", "SSID", "APISID", "SAPISID",
                           "__Secure-3PAPISID", "VISITOR_INFO1_LIVE", "PREF", "YSC"]
            cookie_pairs = [f"{c.name}={c.value}" for c in cj2 if c.name in key_cookies]
            if cookie_pairs:
                cmd.extend(["-H", f"Cookie: {'; '.join(cookie_pairs)}"])
        except Exception:
            pass

    if proxy:
        cmd.extend(["-x", proxy])

    if resume and os.path.exists(output):
        downloaded = os.path.getsize(output)
        if downloaded > 0:
            cmd.extend(["-C", "-"])
            print(f"  Resuming from {downloaded / 1024 / 1024:.1f}MB")

    for attempt in range(3):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout * 5)
            if result.returncode == 0 and os.path.exists(output):
                return output
            err = result.stderr.strip()
            if "403" in err and proxy and attempt == 0:
                print(f"\n  403 with proxy - retrying without proxy...")
                cmd = [c for c in cmd if c != proxy and c != "-x"]
                import time; time.sleep(2)
                continue
            if attempt < 2:
                print(f"\n  Download failed: {err[:100]} - retrying...")
                import time; time.sleep(2)
        except Exception as e:
            if attempt < 2:
                import time; time.sleep(2)

    raise RuntimeError("Download failed after 3 attempts")


def _download_and_mux(result: StreamResult, output: str,
                       cookies_file: str | None, proxy: str | None,
                       timeout: int) -> str:
    """Download video + audio separately and merge with ffmpeg."""
    import os
    import subprocess
    import tempfile

    # Check ffmpeg availability
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise RuntimeError(
            "ffmpeg is required for muxing. Install it with: "
            "apt-get install ffmpeg / brew install ffmpeg"
        )

    # Get video stream (highest quality)
    video_result = get_stream_url(
        result.video_id,
        cookies_file=cookies_file,
        proxy=proxy,
        quality="best",
        audio_only=False,
        verify=False,
        timeout=timeout,
    )

    # Get best audio stream
    audio_result = get_stream_url(
        f"https://www.youtube.com/watch?v={result.video_id}",
        cookies_file=cookies_file,
        proxy=proxy,
        audio_only=True,
        quality="high",
        verify=False,
        timeout=timeout,
    )

    tmp_dir = tempfile.mkdtemp(prefix="aytube_mux_")
    video_path = os.path.join(tmp_dir, f"video_{video_result.itag}.{video_result.container}")
    audio_path = os.path.join(tmp_dir, f"audio_{audio_result.itag}.{audio_result.container}")

    print(f"Downloading video ({video_result.quality})...")
    _download_file(video_result.url, video_path, cookies_file, proxy, timeout,
                   video_result.size, video_result.title)

    print(f"Downloading audio ({audio_result.quality})...")
    _download_file(audio_result.url, audio_path, cookies_file, proxy, timeout,
                   audio_result.size, audio_result.title)

    print("Merging with ffmpeg...")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
            "-c", "copy", "-movflags", "+faststart",
            output
        ], capture_output=True, check=True, timeout=300)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg muxing failed: {e.stderr.decode()[:200]}")
    finally:
        # Cleanup temp files
        for p in [video_path, audio_path]:
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass

    return output


def _show_progress(downloaded: int, total: int, title: str = ""):
    """Show download progress on one line."""
    if total > 0:
        pct = (downloaded / total) * 100
        bar_len = 30
        filled = int(bar_len * downloaded / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        title_short = title[:40] if title else ""
        sys.stdout.write(f"\r  {bar} {pct:5.1f}% {mb:.1f}/{total_mb:.1f} MB {title_short}")
    else:
        mb = downloaded / (1024 * 1024)
        sys.stdout.write(f"\r  Downloading... {mb:.1f} MB")
    sys.stdout.flush()


# ─── Public API: playlist ─────────────────────────────────────────────────

def list_playlist(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> list[dict]:
    """
    List all videos in a YouTube playlist.
    """
    from .fetcher import fetch_page

    html = fetch_page(url, cookies_file=cookies_file, proxy=proxy, timeout=timeout)

    import re, json

    # Extract all JSON blobs from the page
    json_blobs = _extract_all_json(html)

    videos = []
    seen = set()

    def extract_renderer(vr: dict):
        """Extract video info from a renderer dict."""
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

    def _deep_find_text(obj) -> str:
        """Walk values looking for any text content."""
        if isinstance(obj, dict):
            # Direct text keys
            for k in ("simpleText", "text", "content"):
                if k in obj and isinstance(obj[k], str):
                    return obj[k]
            # runs array
            runs = obj.get("runs", [])
            if runs and isinstance(runs[0], dict):
                t = runs[0].get("text", "")
                if t:
                    return t
            # Recurse values
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

    def _deep_find_thumb(obj) -> str:
        """Walk values looking for thumbnail URL."""
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

    def walk(obj):
        """Walk JSON values looking for dicts containing videoId."""
        if isinstance(obj, dict):
            # If this dict has videoId, it's a video entry
            vid = obj.get("videoId") or obj.get("id", "")
            if isinstance(vid, str) and len(vid) == 11:
                extract_renderer(obj)
                return
            # Check known renderer keys (non-obfuscated pages)
            for rtype in ("playlistVideoRenderer", "videoRenderer", "gridVideoRenderer",
                          "compactVideoRenderer", "videoWithContextRenderer",
                          "playlistPanelVideoRenderer"):
                if rtype in obj:
                    vr = obj[rtype]
                    if rtype == "videoWithContextRenderer":
                        vr = vr.get("compactVideoRenderer", vr)
                    extract_renderer(vr)
                    return
            # Recurse into values
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    # Process each JSON blob
    for data in json_blobs:
        walk(data)
        if videos:
            break

    # Regex fallback on raw HTML
    if not videos:
        raw_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        for vid in list(dict.fromkeys(raw_ids)):
            if vid not in seen:
                seen.add(vid)
                videos.append({
                    "video_id": vid,
                    "title": f"Video {vid}",
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "position": str(len(videos) + 1),
                    "thumbnail": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                })

    # Innertube API fallback disabled (requires authentication token)
    # if not videos:
    #     m = re.search(r'[?&]list=([^&]+)', url)
    #     if m:
    #         try:
    #             from .innertube_extra import fetch_playlist
    #             pl_id = m.group(1)
    #             videos = fetch_playlist(pl_id, cookies_file=cookies_file, proxy=proxy,
    #                                     timeout=timeout, max_results=100)
    #             print(f"  Innertube playlist: found {len(videos)} videos")
    #         except Exception as e:
    #             print(f"  [DEBUG] Innertube playlist error: {e}")

    return videos


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


# ─── Public API: subtitles ─────────────────────────────────────────────────

def list_subtitles(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict:
    """
    List available subtitles/captions for a YouTube video.

    Parameters
    ----------
    url : str
        YouTube video URL.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    dict
        Keys are language codes, values are lists of caption tracks.
        Each track has: url, lang, lang_name, is_auto, is_translated.
    """
    from .fetcher import fetch_page
    from .player import get_player_response

    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    html = fetch_page(video_id, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
    pr = get_player_response(html)

    captions_data = pr.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
    caption_tracks = captions_data.get("captionTracks", [])

    result = {}
    for track in caption_tracks:
        lang_code = track.get("languageCode", "")
        lang_name = track.get("name", {}).get("simpleText", lang_code)
        track_url = track.get("baseUrl", "")
        is_auto = track.get("kind", "") == "asr"
        is_translated = track.get("isTranslated", False)

        if lang_code not in result:
            result[lang_code] = []

        result[lang_code].append({
            "url": track_url,
            "lang": lang_code,
            "lang_name": lang_name,
            "is_auto": is_auto,
            "is_translated": is_translated,
        })

    # Also check for translation tracks
    translation_langs = captions_data.get("translationLanguages", [])
    for lang in translation_langs:
        lang_code = lang.get("languageCode", "")
        lang_name = lang.get("name", {}).get("simpleText", lang_code)
        if lang_code not in result:
            result[lang_code] = []

    return result
