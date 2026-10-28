"""
aytube.extractor - Core stream extraction orchestrator, format resolution, and caching.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from typing import Any

from .cipher import (
    apply_n_parameter,
    decipher,
    decode_signature_cipher,
    extract_cipher_function,
    extract_key,
    extract_n_function,
    has_cipher,
    has_n_parameter,
    resolve_signature_format,
)
from .innertube import fetch_player_response, fetch_playlist
from .stream import (
    _ITAG_TYPE_MAP,
    StreamResult,
    codec_from_mime,
    find_best_stream,
    parse_mime_type,
    verify_stream,
)
from .utils import (
    detect_bot_challenge,
    extract_player_js_url,
    extract_video_id,
    fetch_page,
    fetch_player_js,
    find_cookies_path,
    get_player_response,
)

# In-memory format cache (TTL 300s) to reduce redundant requests
_FORMAT_CACHE: dict[str, tuple[list[dict], Any, dict[int, int], float, str]] = {}
_CACHE_TTL = 300


def _build_format_url(base_url: str, sig_value: str, sig_param_name: str, fmt: dict) -> str:
    """Build stream URL for adaptive format by updating itag, sparams, and appending sig."""
    target_itag = fmt.get("itag", 0)
    if not target_itag or "?" not in base_url:
        return ""

    prefix, query = base_url.split("?", 1)
    existing_itag = ""
    for param in query.split("&"):
        if param.startswith("itag="):
            existing_itag = param.split("=", 1)[1]
            break

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
            sp_items = val.split(",")
            sp_items = [str(target_itag) if p == existing_itag else p for p in sp_items]
            param_dict["sparams"] = ",".join(sp_items)
        else:
            param_dict[key] = val

    if sig_value:
        param_dict[sig_param_name] = sig_value

    return f"{prefix}?{'&'.join(f'{k}={v}' for k, v in param_dict.items())}"


def _process_formats_html(all_formats: list[dict], html: str, cookies: str | None, proxy: str | None, timeout: int):
    """Decipher signatureCipher and resolve playable URLs via HTML + player JS."""
    needs_c = has_cipher(all_formats)
    needs_n = has_n_parameter(all_formats)
    n_func = None

    if needs_c or needs_n:
        html_key = extract_key(html=html)
        if html_key:
            needs_c = True

        try:
            player_js_url = extract_player_js_url(html)
        except RuntimeError:
            player_js_url = None

        js_code = None
        if player_js_url:
            try:
                js_code = fetch_player_js(player_js_url, cookies_file=cookies, proxy=proxy, timeout=timeout)
            except Exception:
                pass

        if needs_c and js_code:
            cipher_func = extract_cipher_function(js_code, aes_key=html_key or None)
            if cipher_func:
                _sig_base_url = ""
                _sig_deciphered = ""
                _sig_sp = "signature"

                for fmt in all_formats:
                    sig_info = decode_signature_cipher(fmt.pop("signatureCipher", "")) if fmt.get("signatureCipher") else {
                        "s": fmt.pop("s", ""),
                        "sp": fmt.get("sp", "signature"),
                        "url": fmt.get("url", ""),
                    }
                    sig = sig_info.get("s", "")
                    if sig:
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
                        except Exception:
                            pass
                    fmt.pop("sp", None)
                    fmt.pop("s", None)

                if _sig_base_url and _sig_deciphered:
                    for fmt in all_formats:
                        if not fmt.get("url"):
                            fmt["url"] = _build_format_url(_sig_base_url, _sig_deciphered, _sig_sp, fmt)

        if needs_n and js_code:
            n_func = extract_n_function(js_code)

    for fmt in all_formats:
        if not fmt.get("url"):
            fmt["url"] = resolve_signature_format(fmt)

    return all_formats, n_func


def get_stream_url(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    quality: str | None = None,
    audio_only: bool = False,
    verify: bool = True,
    timeout: int = 30,
    method: str = "auto",
) -> StreamResult:
    """
    Extract direct Google Video stream URL from a YouTube URL or video ID.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    cookies = find_cookies_path(cookies_file)

    # 1. Cache hit check
    cache_key = f"{video_id}:{cookies or ''}:{proxy or ''}:{method}"
    now = time.time()
    cached = _FORMAT_CACHE.get(cache_key)
    if cached:
        cached_formats, _, cached_cl, cached_ts, cached_title = cached
        if now - cached_ts < _CACHE_TTL:
            result = find_best_stream(
                cached_formats, quality=quality, audio_only=audio_only, is_live=False, itag_content_length=cached_cl
            )
            result.title = cached_title
            result.video_id = video_id
            if result.itag and result.itag in cached_cl:
                result.size = cached_cl[result.itag]
            return result

    use_html = method in ("auto", "html")
    use_innertube = method in ("auto", "innertube")
    if method == "html":
        use_innertube = False
    elif method == "innertube":
        use_html = False

    player_response = None
    html = None
    n_func = None
    fetch_method = None

    # Priority 1: Innertube API (pre-signed unencrypted URLs)
    if use_innertube:
        try:
            resp = fetch_player_response(video_id, cookies_file=cookies, proxy=proxy, timeout=timeout)
            sd = resp.get("streamingData", {})
            fmts = [f for f in sd.get("formats", []) + sd.get("adaptiveFormats", []) if f.get("url")]
            if fmts:
                player_response = resp
                fetch_method = "innertube"
        except Exception:
            player_response = None

    # Priority 2: HTML scraping fallback
    if not player_response and use_html:
        last_exc = None
        for attempt in range(2):
            try:
                html = fetch_page(video_id, cookies_file=cookies, proxy=proxy, timeout=timeout)
                if detect_bot_challenge(html):
                    if attempt == 0 and not cookies:
                        cookies = find_cookies_path(cookies_file)
                        if cookies:
                            time.sleep(1)
                            continue
                    raise RuntimeError("YouTube returned a bot verification challenge. Netscape cookies are required.")
                player_response = get_player_response(html)
                fetch_method = "html"
                break
            except Exception as exc:
                last_exc = exc
                if attempt == 0 and not cookies:
                    cookies = find_cookies_path(cookies_file)
                    if cookies:
                        time.sleep(1)
                        continue
                raise
        if not player_response:
            raise last_exc or RuntimeError("Failed to fetch YouTube page.")

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
            raise ValueError("Age-restricted video. Netscape cookies file required.")
        if status == "LIVE_STREAM_OFFLINE":
            raise ValueError("This live stream is currently offline.")
        if status == "UNPLAYABLE":
            raise ValueError(f"Video is unplayable: {reason}")
        raise ValueError(f"Cannot play this video: {reason}")

    itag_content_length = {}
    for fmt in all_formats:
        itag = fmt.get("itag")
        cl = fmt.get("contentLength")
        if itag and cl:
            itag_content_length[itag] = int(cl)

    if fetch_method == "innertube":
        for fmt in all_formats:
            fmt.pop("sp", None)
            fmt.pop("s", None)
            if not fmt.get("url"):
                fmt["url"] = resolve_signature_format(fmt)
    else:
        all_formats, n_func = _process_formats_html(all_formats, html, cookies, proxy, timeout)

    result = find_best_stream(
        all_formats, quality=quality, audio_only=audio_only, is_live=is_live, itag_content_length=itag_content_length
    )
    result.title = title
    result.video_id = video_id

    # Anti-throttling n-parameter transformation
    if result.url and n_func:
        for fmt in all_formats:
            c = fmt.get("signatureCipher", "")
            if "&n=" in c:
                parsed_c = decode_signature_cipher(c)
                n_val = parsed_c.get("n", "")
                if n_val:
                    result.url = apply_n_parameter(result.url, n_val, n_func)
                    break

    # Reachability verification if requested
    if verify and result.url:
        checked_size = verify_stream(result.url, cookies_file=cookies, proxy=proxy, timeout=timeout)
        if checked_size > 0 and result.size == 0:
            result.size = checked_size

    if any(f.get("url") for f in all_formats):
        _FORMAT_CACHE[cache_key] = (all_formats, n_func, itag_content_length, time.time(), title)

    return result


def list_formats(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    audio_only: bool = False,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """
    List all available video and audio streams for a video.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    cookies = find_cookies_path(cookies_file)
    all_formats = []

    try:
        resp = fetch_player_response(video_id, cookies_file=cookies, proxy=proxy, timeout=timeout)
        sd = resp.get("streamingData", {})
        innertube_fmts = sd.get("formats", []) + sd.get("adaptiveFormats", [])
        if any(f.get("url") for f in innertube_fmts):
            all_formats = [dict(f) for f in innertube_fmts]
    except Exception:
        pass

    if not all_formats:
        page_html = fetch_page(video_id, cookies_file=cookies, proxy=proxy, timeout=timeout)
        pr = get_player_response(page_html)
        sd = pr.get("streamingData", {})
        raw_fmts = sd.get("formats", []) + sd.get("adaptiveFormats", [])
        all_formats = [dict(f) for f in raw_fmts]
        try:
            all_formats, _ = _process_formats_html(all_formats, page_html, cookies, proxy, timeout)
        except Exception:
            for fmt in all_formats:
                if not fmt.get("url"):
                    fmt["url"] = resolve_signature_format(fmt)

    results = []
    for fmt in all_formats:
        mime, codecs = parse_mime_type(fmt.get("mimeType", ""))
        itag = fmt.get("itag", 0)
        height = fmt.get("height", 0) or 0
        ftype = "audio" if fmt.get("mimeType", "").startswith("audio") else "video"

        if audio_only and ftype != "audio":
            continue

        size = int(fmt.get("contentLength", 0) or 0)
        bitrate = fmt.get("bitrate", 0) or 0
        fps = fmt.get("fps", 0) or 0

        if ftype == "audio":
            mapped = _ITAG_TYPE_MAP.get(itag)
            if mapped and mapped[0] == "audio":
                quality_label = mapped[2]
            else:
                aq = fmt.get("audioQuality", "")
                quality_label = "high" if "high" in aq.lower() else "medium" if "medium" in aq.lower() else "low"
        else:
            quality_label = f"{height}p" if height else fmt.get("qualityLabel", "")

        is_hdr = any(hdr in (codecs or "").lower() for hdr in ["hdr", "bt2020", "smpte2084"])
        is_vo = fmt.get("audioCodec") == "none" or (ftype == "video" and not fmt.get("audioCodec"))

        results.append({
            "itag": itag,
            "quality": quality_label,
            "container": mime,
            "video_codec": codec_from_mime(codecs, "video") or fmt.get("video_codec") or fmt.get("videoCodec", ""),
            "audio_codec": codec_from_mime(codecs, "audio") or fmt.get("audio_codec") or fmt.get("audioCodec", ""),
            "mime_type": fmt.get("mimeType", ""),
            "size": size,
            "bitrate": bitrate,
            "fps": fps,
            "is_hdr": is_hdr,
            "is_video_only": is_vo,
            "url": fmt.get("url", ""),
            "raw": fmt,
        })

    return results


def list_playlist(
    url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
    max_results: int = 100,
) -> list[dict[str, Any]]:
    """List videos in a YouTube playlist."""
    playlist_id = url
    if "list=" in url:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        playlist_id = params.get("list", [url])[0]

    return fetch_playlist(playlist_id, cookies_file=cookies_file, proxy=proxy, timeout=timeout, max_results=max_results)
