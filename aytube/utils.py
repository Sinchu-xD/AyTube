"""
aytube.utils - URL parsing, HTTP fetching, configuration, and helpers.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Regex patterns for YouTube video IDs
_WATCH_RE = re.compile(r'(?:v=|/v/|/watch\?v=|/embed/|/shorts/)([A-Za-z0-9_-]{11})')
_SHORT_URL_RE = re.compile(r'youtu\.be/([A-Za-z0-9_-]{11})')
_RAW_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')

# Patterns to locate ytInitialPlayerResponse JSON in HTML
_INITIAL_PLAYER_RE = re.compile(
    r'ytInitialPlayerResponse\s*=\s*({.+?})\s*;\s*(?:var\s+meta|</script>|$)',
    re.DOTALL,
)
_FALLBACK_PLAYER_RE = re.compile(
    r'ytInitialPlayerResponse\s*=\s*({.+?})\s*;',
    re.DOTALL,
)

# Common names for exported Netscape cookies
_COOKIE_NAMES = (
    "cookies.txt",
    "cookie.txt",
    "cookies_file",
    "cookies",
    "youtube_cookies.txt",
    "youtube.com_cookies.txt",
)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
}

# Configuration defaults
CONFIG_DIR = os.path.expanduser("~/.config/aytube")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_CONFIG = {
    "cookies_file": "",
    "proxy": "",
    "default_quality": "best",
    "default_audio_only": False,
    "default_output_dir": ".",
    "default_timeout": 30,
    "verify_streams": True,
}


def extract_video_id(url: str) -> str | None:
    """
    Extract the 11-character YouTube video ID from any format or passthrough raw ID.

    Supports:
        - https://www.youtube.com/watch?v=dQw4w9WgXcQ
        - https://youtu.be/dQw4w9WgXcQ
        - https://www.youtube.com/shorts/dQw4w9WgXcQ
        - https://www.youtube.com/embed/dQw4w9WgXcQ
        - https://www.youtube.com/v/dQw4w9WgXcQ
        - dQw4w9WgXcQ (direct 11-char ID)
    """
    if not url:
        return None
    url = url.strip()

    if _RAW_ID_RE.fullmatch(url):
        return url

    if "youtu.be" in url:
        m = _SHORT_URL_RE.search(url)
        if m:
            return m.group(1)

    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        v = qs.get("v", [])
        if v and len(v[0]) == 11:
            return v[0]
    except Exception:
        pass

    m = _WATCH_RE.search(url)
    if m:
        return m.group(1)

    return None


def find_cookies_path(cookies_file: str | None = None) -> str | None:
    """
    Locate valid cookies file from argument or standard search locations.
    """
    if cookies_file and os.path.isfile(cookies_file):
        return os.path.abspath(cookies_file)

    cfg = load_config()
    cfg_cookie = cfg.get("cookies_file")
    if cfg_cookie and os.path.isfile(cfg_cookie):
        return os.path.abspath(cfg_cookie)

    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [
        os.getcwd(),
        os.path.join(pkg_dir, ".."),
        CONFIG_DIR,
        os.path.expanduser("~"),
    ]

    for d in search_dirs:
        for name in _COOKIE_NAMES:
            candidate = os.path.normpath(os.path.join(d, name))
            if os.path.isfile(candidate):
                return candidate
    return None


def build_opener(cookies_file: str | None = None, proxy: str | None = None) -> urllib.request.OpenerDirector:
    """
    Build a standard urllib OpenerDirector with cookie jar and proxy support.
    """
    handlers: list[Any] = []
    cf = find_cookies_path(cookies_file)
    if cf:
        try:
            cj = http.cookiejar.MozillaCookieJar()
            cj.load(cf, ignore_discard=True, ignore_expires=True)
            handlers.append(urllib.request.HTTPCookieProcessor(cj))
        except Exception:
            pass

    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))

    return urllib.request.build_opener(*handlers)


def detect_bot_challenge(html: str) -> bool:
    """Check if YouTube returned a bot verification / captcha response."""
    if "Sign in to confirm you're not a bot" in html:
        return True
    if 'id="captcha"' in html or "/Captcha" in html:
        return True
    return False


def fetch_page(
    video_id: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> str:
    """
    Fetch the watch page HTML with exponential backoff on rate-limits.
    """
    if video_id.startswith(("http://", "https://")):
        url = video_id
    else:
        url = f"https://www.youtube.com/watch?v={video_id}"

    attempts: list[str | None] = []
    cf = find_cookies_path(cookies_file)
    if cf:
        attempts.append(cf)
    attempts.append(None)

    last_exc: Exception | None = None
    for i, c_path in enumerate(attempts):
        if i > 0:
            time.sleep(min(2 ** i, 8))
        try:
            opener = build_opener(cookies_file=c_path, proxy=proxy)
            req = urllib.request.Request(url, headers=_DEFAULT_HEADERS)
            resp = opener.open(req, timeout=timeout)
            html = resp.read().decode("utf-8", errors="replace")
            resp.close()

            if detect_bot_challenge(html):
                last_exc = RuntimeError(
                    "YouTube returned a bot verification challenge. "
                    "Provide a valid Netscape cookies.txt file."
                )
                continue
            return html
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429:
                wait_time = min(2 ** (i + 2), 30)
                print(f"  Rate-limited (429), retrying in {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)
                continue
            if exc.code not in (403, 503):
                raise
        except urllib.error.URLError as exc:
            last_exc = exc

    if last_exc:
        if isinstance(last_exc, urllib.error.HTTPError) and last_exc.code == 429:
            raise ValueError(
                "Rate-limited by YouTube (HTTP 429). Use a proxy or cookies_file."
            ) from last_exc
        raise last_exc

    raise RuntimeError("Failed to fetch YouTube page.")


def get_player_response(html: str) -> dict:
    """
    Extract ytInitialPlayerResponse JSON object from HTML.
    """
    m = _INITIAL_PLAYER_RE.search(html) or _FALLBACK_PLAYER_RE.search(html)
    if not m:
        raise RuntimeError(
            "Could not find ytInitialPlayerResponse in page HTML. "
            "YouTube page structure may have changed."
        )

    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse ytInitialPlayerResponse: {exc}") from exc


def extract_player_js_url(html: str) -> str:
    """Extract player JS URL from watch page HTML."""
    m = re.search(r'["\'](/s/player/[^"\']+/[a-z_]+\.js)["\']', html)
    if m:
        return "https://www.youtube.com" + m.group(1)

    m = re.search(r'(/s/player/[a-zA-Z0-9_-]+/[a-z_]+\.js)', html)
    if m:
        return "https://www.youtube.com" + m.group(1)

    raise RuntimeError("Could not find player JS URL in YouTube watch page.")


def fetch_player_js(
    player_js_url: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> str:
    """Fetch player JavaScript code."""
    opener = build_opener(cookies_file, proxy)
    headers = {
        **_DEFAULT_HEADERS,
        "Accept": "*/*",
        "Referer": "https://www.youtube.com/",
    }
    req = urllib.request.Request(player_js_url, headers=headers)
    resp = opener.open(req, timeout=timeout)
    code = resp.read().decode("utf-8", errors="replace")
    resp.close()
    return code


# ── Configuration Management ──────────────────────────────────────────────────

def load_config() -> dict:
    """Load settings from ~/.config/aytube/config.json with default fallbacks."""
    if not os.path.isfile(CONFIG_FILE):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> str:
    """Save configuration to disk."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    merged = dict(DEFAULT_CONFIG)
    merged.update(config)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    return CONFIG_FILE


def get_config(key: str, default: Any = None) -> Any:
    """Get single configuration key."""
    return load_config().get(key, default)


def set_config(key: str, value: Any) -> dict:
    """Set single configuration key and save."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    return cfg


def show_config():
    """Print current configuration to stdout."""
    print("aytube configuration:")
    for k, v in load_config().items():
        print(f"  {k}: {v}")


def setup_wizard():
    """Interactive CLI setup for user settings."""
    cfg = load_config()
    print("=" * 45)
    print("  aytube Interactive Setup")
    print("=" * 45)

    c_path = input(f"Cookies file path [{cfg.get('cookies_file')}]: ").strip()
    if c_path:
        cfg["cookies_file"] = c_path

    proxy = input(f"Default proxy [{cfg.get('proxy')}]: ").strip()
    if proxy:
        cfg["proxy"] = proxy

    q = input(f"Default quality [{cfg.get('default_quality')}]: ").strip()
    if q:
        cfg["default_quality"] = q

    path = save_config(cfg)
    print(f"\nConfiguration saved to: {path}")


# ── String and Formatting Helpers ─────────────────────────────────────────────

def safe_filename(name: str, max_len: int = 100) -> str:
    """Sanitize arbitrary video titles for use as filesystem file names."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "video"


def show_progress(downloaded: int, total: int, title: str = ""):
    """Render a clean single-line download progress bar."""
    if total > 0:
        pct = (downloaded / total) * 100
        bar_len = 30
        filled = int(bar_len * downloaded / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        d_mb = downloaded / 1024 / 1024
        t_mb = total / 1024 / 1024
        t_disp = f" - {title[:20]}" if title else ""
        sys.stdout.write(f"\r  [{bar}] {pct:5.1f}% ({d_mb:5.1f}/{t_mb:5.1f}MB){t_disp}")
    else:
        d_mb = downloaded / 1024 / 1024
        sys.stdout.write(f"\r  {d_mb:6.1f} MB downloaded...")
    sys.stdout.flush()


def format_duration(seconds: int | float) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS."""
    sec = int(seconds or 0)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
