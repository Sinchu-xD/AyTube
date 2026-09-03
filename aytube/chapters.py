"""
Extract video chapters/timestamps from YouTube videos.
"""
from __future__ import annotations

import re


def get_chapters(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> list[dict]:
    """
    Get chapters/timestamps for a YouTube video.

    Parameters
    ----------
    video_id : str
        YouTube video ID.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    list[dict]
        List of chapters with: title, start_time (seconds), start_time_formatted (MM:SS or HH:MM:SS).
    """
    from .fetcher import fetch_page
    from .player import get_player_response

    html = fetch_page(video_id, cookies_file=cookies_file, proxy=proxy, timeout=timeout)
    pr = get_player_response(html)

    # Try to get chapters from player response
    chapters_data = pr.get("chapters", {})

    if chapters_data:
        chapter_items = chapters_data.get("playerAttachableChaptersRenderer", {})
        if chapter_items:
            chapters = []
            for item in chapter_items:
                title = item.get("chapterRenderer", {}).get("title", {}).get("simpleText", "")
                start_time = item.get("chapterRenderer", {}).get("timeRangeStartMillis", 0)
                chapters.append({
                    "title": title,
                    "start_time": start_time // 1000,
                    "start_time_formatted": _format_time(start_time // 1000),
                })
            if chapters:
                return chapters

    # Fallback: parse from description
    description = pr.get("videoDetails", {}).get("shortDescription", "")
    return _parse_description_chapters(description)


def _parse_description_chapters(description: str) -> list[dict]:
    """
    Parse chapters from video description text.
    Looks for patterns like:
    0:00 Intro
    1:23 First topic
    3:45 Second topic
    """
    chapters = []
    lines = description.split("\n")

    # Pattern: timestamp at start of line (e.g., "0:00", "1:23", "1:02:30")
    timestamp_pattern = re.compile(r'^(\d{1,2}:)?(\d{1,2}):(\d{2})\s+(.+)')

    for line in lines:
        line = line.strip()
        match = timestamp_pattern.match(line)
        if match:
            hours = int(match.group(1)[:-1]) if match.group(1) else 0
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            title = match.group(4).strip()

            total_seconds = hours * 3600 + minutes * 60 + seconds

            chapters.append({
                "title": title,
                "start_time": total_seconds,
                "start_time_formatted": _format_time(total_seconds),
            })

    return chapters


def _format_time(seconds: int) -> str:
    """Format seconds to HH:MM:SS or MM:SS."""
    if not seconds:
        return "0:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
