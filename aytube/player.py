"""
Player response parsing - extract ytInitialPlayerResponse JSON from watch page HTML.
"""

import json
import re


# Try multiple patterns to find the ytInitialPlayerResponse JSON
_INITIAL_DATA_RE = re.compile(
    r'ytInitialPlayerResponse\s*=\s*({.+?})\s*;\s*(?:var\s+meta|</script>|$)',
    re.DOTALL,
)

# Fallback: look for it inside a script tag more broadly
_FALLBACK_RE = re.compile(
    r'ytInitialPlayerResponse\s*=\s*({.+?})\s*;',
    re.DOTALL,
)


def get_player_response(html: str) -> dict:
    """
    Extract the ytInitialPlayerResponse JSON object from YouTube HTML.

    This JSON contains all the metadata we need: video title, description,
    streamingData (formats + adaptiveFormats), and playability status.

    Returns the parsed dictionary.
    """
    m = _INITIAL_DATA_RE.search(html)
    if not m:
        m = _FALLBACK_RE.search(html)
    if not m:
        raise RuntimeError(
            "Could not find ytInitialPlayerResponse in page HTML. "
            "YouTube may have changed their page structure."
        )

    json_str = m.group(1)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Failed to parse ytInitialPlayerResponse JSON: {exc}"
        ) from exc

    return data
