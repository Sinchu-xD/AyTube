"""
URL parsing - extract video ID from any YouTube URL format.
"""

import re
from urllib.parse import urlparse, parse_qs

# Patterns that YouTube uses for video identification
WATCH_RE = re.compile(r'(?:v=|/v/|/watch\?v=|/embed/|/shorts/)([A-Za-z0-9_-]{11})')
URL_ID_RE = re.compile(r'youtu\.be/([A-Za-z0-9_-]{11})')
DEEP_SCAN_RE = re.compile(r'([A-Za-z0-9_-]{11})')

# Regex that matches common (non-YouTube) video ID strings so we don't
# accidentally pick up unrelated 11-char codes from a long URL.
_URL_TLD = re.compile(r'[A-Za-z0-9_-]{1,30}\.[A-Za-z]{2,}')


def extract_video_id(url: str) -> str | None:
    """
    Extract a YouTube video ID from a URL.

    Supports:
        - https://www.youtube.com/watch?v=dQw4w9WgXcQ
        - https://youtube.com/watch?v=dQw4w9WgXcQ&list=...
        - https://m.youtube.com/watch?v=dQw4w9WgXcQ
        - https://youtu.be/dQw4w9WgXcQ
        - https://youtu.be/dQw4w9WgXcQ?t=30
        - https://www.youtube.com/embed/dQw4w9WgXcQ
        - https://www.youtube.com/v/dQw4w9WgXcQ
        - https://www.youtube.com/shorts/dQw4w9WgXcQ
        - https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ
    """
    if not url:
        return None

    url = url.strip()

    # Direct youtu.be short links
    if 'youtu.be' in url:
        m = URL_ID_RE.search(url)
        if m:
            return m.group(1)
        return None

    # Parse query parameters for v=VIDEO_ID
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        v = qs.get('v', [])
        if v and len(v[0]) == 11:
            return v[0]
    except Exception:
        pass

    # Pattern-based extraction from path components
    m = WATCH_RE.search(url)
    if m:
        return m.group(1)

    return None
