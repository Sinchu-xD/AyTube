"""
fetcher.py - HTTP fetching for aytube.

Handles fetching the YouTube watch page, player JS, and making
innertube API calls. Uses stdlib urllib with cookie and proxy support.
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
import http.cookiejar
from urllib.parse import urlencode


def _build_opener(cookies_file=None, proxy=None):
    """Build a urllib opener with optional cookies and proxy."""
    handlers = []
    if cookies_file:
        cj = http.cookiejar.MozillaCookieJar()
        cj.load(cookies_file, ignore_discard=True, ignore_expires=True)
        handlers.append(urllib.request.HTTPCookieProcessor(cj))
    if proxy:
        handlers.append(urllib.request.ProxyHandler(
            {'http': proxy, 'https': proxy}
        ))
    return urllib.request.build_opener(*handlers)


_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'identity',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}


def fetch_page(video_id: str, cookies_file=None, proxy=None,
               timeout: int = 30) -> str:
    """
    Fetch the YouTube watch page HTML.

    Parameters
    ----------
    video_id : str
        YouTube video ID.
    cookies_file : str | None
        Path to Netscape-format cookies_file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    str
        HTML content of the watch page.
    """
    # Accept full URLs or video IDs
    if video_id.startswith("http://") or video_id.startswith("https://"):
        url = video_id
    else:
        url = f'https://www.youtube.com/watch?v={video_id}'

    # Build list of attempts: start with what was passed, then auto-discover
    attempts = []
    if cookies_file:
        attempts.append(cookies_file)
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.join(here, '..', 'cookies_file'),
        os.path.join(os.getcwd(), 'cookies_file'),
        os.path.expanduser('~/.config/aytube/cookies_file'),
    ]:
        p = os.path.normpath(candidate)
        if os.path.isfile(p) and p not in attempts:
            attempts.append(p)

    last_err = None
    for i, cf in enumerate(attempts):
        if i > 0:
            time.sleep(min(2 ** i, 16))

        try:
            opener = _build_opener(cookies_file=cf, proxy=proxy)
            req = urllib.request.Request(url, headers=_HEADERS)
            resp = opener.open(req, timeout=timeout)
            html = resp.read().decode('utf-8', errors='replace')
            resp.close()

            # Detect bot challenge pages
            if _is_bot_challenge(html):
                last_err = RuntimeError(
                    "YouTube returned a bot verification page. "
                    "Try providing a cookies_file with an authenticated session."
                )
                continue

            return html
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code == 429:
                wait = min(2 ** (i + 2), 60)
                print(f"  Rate limited (429), waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if exc.code not in (403, 503):
                raise
        except urllib.error.URLError as exc:
            last_err = exc

    if last_err:
        if isinstance(last_err, urllib.error.HTTPError) and last_err.code == 429:
            raise ValueError(
                "Rate-limited by YouTube (HTTP 429). "
                "Wait a few minutes or try a different proxy."
            ) from last_err
        raise last_err

    raise RuntimeError("Failed to fetch page after retries")


def _is_bot_challenge(html: str) -> bool:
    """Detect if the response is a bot verification page."""
    # YouTube shows "Sign in to confirm you're not a bot"
    if "Sign in to confirm you're not a bot" in html:
        return True
    # Captcha challenge
    if 'id="captcha"' in html or '/Captcha' in html:
        return True
    return False


def extract_player_js_url(html: str) -> str:
    """
    Extract the player JS URL from the watch page HTML.

    Returns the full URL to player_*.js or similar.
    """
    # Pattern 1: /s/player/HASH/player_*.js
    m = re.search(
        r'["\'](/s/player/[^"\']+/[a-z_]+\.js)["\']',
        html
    )
    if m:
        return 'https://www.youtube.com' + m.group(1)

    # Pattern 2: /s/player/HASH/player_*.js (without quotes)
    m = re.search(
        r'(/s/player/[a-zA-Z0-9_-]+/[a-z_]+\.js)',
        html
    )
    if m:
        return 'https://www.youtube.com' + m.group(1)

    raise RuntimeError(
        'Could not find player JS URL in page. '
        'YouTube may have changed their page structure.'
    )


def fetch_player_js(player_js_url: str, cookies_file=None,
                    proxy=None, timeout: int = 30) -> str:
    """
    Fetch the player JavaScript file.

    Parameters
    ----------
    player_js_url : str
        Full URL to the player JS file.
    cookies_file : str | None
        Path to Netscape-format cookies_file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    str
        JavaScript source code.
    """
    opener = _build_opener(cookies_file, proxy)
    js_headers = {
        'User-Agent': (
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        ),
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
        'Referer': 'https://www.youtube.com/',
        'Connection': 'keep-alive',
    }
    req = urllib.request.Request(player_js_url, headers=js_headers)
    resp = opener.open(req, timeout=timeout)
    js_code = resp.read().decode('utf-8', errors='replace')
    resp.close()
    return js_code


def fetch_player_response_innertube(video_id: str, cookies_file=None,
                                     proxy=None, timeout: int = 30) -> dict:
    """
    Fetch streaming data via the innertube API.

    This can return streaming data with unencrypted URLs,
    bypassing the need for signature deciphering.

    Returns the player response JSON as a dict, or None on failure.
    """
    # First get the watch page to extract necessary data
    html = fetch_page(video_id, cookies_file=cookies_file,
                      proxy=proxy, timeout=timeout)

    # Extract initial data
    # Get the ytcfg data
    cfg = {}
    cfg_m = re.search(r'ytcfg\.set\((\{.+?\})\);', html, re.DOTALL)
    if cfg_m:
        try:
            cfg = json.loads(cfg_m.group(1))
        except json.JSONDecodeError:
            pass

    # Get the innertube API key
    api_key = cfg.get('INNERTUBE_API_KEY', '')
    if not api_key:
        # Try alternate patterns
        key_m = re.search(r'INNERTUBE_API_KEY\s*:\s*"([^"]+)"', html)
        if key_m:
            api_key = key_m.group(1)
        else:
            key_m = re.search(r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"', html)
            if key_m:
                api_key = key_m.group(1)

    if not api_key:
        return None

    # Get visitor data
    visitor_data = cfg.get('VISITOR_DATA', '')
    if not visitor_data:
        vd_m = re.search(r'visitorData"\s*:\s*"([^"]+)"', html)
        if vd_m:
            visitor_data = vd_m.group(1)

    # Build the innertube API request body
    context = {
        'context': {
            'client': {
                'clientName': cfg.get('INNERTUBE_CLIENT_NAME', 'WEB'),
                'clientVersion': cfg.get('INNERTUBE_CLIENT_VERSION', '2.20250828.01.00'),
                'hl': 'en',
                'gl': 'US',
                'remoteHost': '',
                'deviceMake': '',
                'deviceModel': '',
            },
            'user': {
                'lockedSafetyMode': False,
            },
            'request': {
                'useSsl': True,
            },
        },
        'videoId': video_id,
        'contentCheckOk': True,
        'racyCheckOk': True,
    }

    if visitor_data:
        context['context']['client']['visitorData'] = visitor_data

    api_url = (
        f'https://www.youtube.com/youtubei/v1/player?'
        f'key={api_key}&prettyPrint=false'
    )

    opener = _build_opener(cookies_file, proxy)
    req = urllib.request.Request(
        api_url,
        data=json.dumps(context).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'X-YouTube-Client-Name': str(cfg.get('INNERTUBE_CLIENT_NAME', '1')),
            'X-YouTube-Client-Version': cfg.get('INNERTUBE_CLIENT_VERSION', ''),
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
            ),
            'Origin': 'https://www.youtube.com',
            'Referer': f'https://www.youtube.com/watch?v={video_id}',
        },
    )

    try:
        resp = opener.open(req, timeout=timeout)
        data = json.loads(resp.read().decode('utf-8'))
        resp.close()
        return data.get('playerResponse', {})
    except Exception:
        return None


def get_ytcfg(html: str) -> dict:
    """Extract ytcfg configuration from page HTML."""
    cfg = {}
    cfg_m = re.search(r'ytcfg\.set\((\{.+?\})\);', html, re.DOTALL)
    if cfg_m:
        try:
            cfg = json.loads(cfg_m.group(1))
        except json.JSONDecodeError:
            pass
    return cfg
