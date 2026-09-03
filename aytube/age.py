"""
Age-restricted video bypass for aytube.

YouTube's embed player (youtube.com/embed/VIDEO_ID) doesn't enforce
age checks, so we can fetch streaming data from there for age-restricted
videos when cookies are not available.
"""
from __future__ import annotations

import re
import json


def bypass_age_check(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict | None:
    """
    Attempt to bypass age check by fetching the embedded player page.

    The embed player at youtube.com/embed/VIDEO_ID doesn't enforce
    age verification, but may still require login for some content.

    Parameters
    ----------
    video_id : str
        YouTube video ID.
    cookies_file : str | None
        Path to cookies_file file (recommended).
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    dict | None
        Player response dict if successful, None otherwise.
    """
    from .fetcher import fetch_page
    from .player import get_player_response

    # Try embed URL first (no age check)
    embed_url = f"https://www.youtube.com/embed/{video_id}"

    try:
        html = fetch_page(video_id, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
        pr = get_player_response(html)

        # Check if we got valid streaming data
        sd = pr.get("streamingData", {})
        if sd.get("formats") or sd.get("adaptiveFormats"):
            return pr

        # Check if age check is still blocking
        ps = pr.get("playabilityStatus", {})
        status = ps.get("status", "")

        if status in ("AGE_CHECK_REQUIRED", "AGE_VERIFICATION_REQUIRED", "LOGIN_REQUIRED"):
            # Try with embed approach
            return _try_embed_player(video_id, cookies_file, proxy, timeout)

        return pr

    except Exception:
        # Try embed as fallback
        return _try_embed_player(video_id, cookies_file, proxy, timeout)


def _try_embed_player(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict | None:
    """
    Try fetching via the embed player which bypasses age checks.
    """
    from .fetcher import fetch_page
    from .player import get_player_response

    embed_url = f"https://www.youtube.com/embed/{video_id}"

    try:
        html = fetch_page(embed_url, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
        pr = get_player_response(html)

        sd = pr.get("streamingData", {})
        if sd.get("formats") or sd.get("adaptiveFormats"):
            return pr

        return None

    except Exception:
        return None
