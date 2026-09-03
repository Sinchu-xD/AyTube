"""
Download with resume support for aytube.

Allows continuing interrupted downloads from where they left off.
"""
from __future__ import annotations

import os
import time
import urllib.request
import http.cookiejar


def download_with_resume(
    url: str,
    output: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 60,
    chunk_size: int = 1024 * 1024,  # 1MB
    title: str = "",
) -> str:
    """
    Download a file with resume support.

    If the output file already exists, attempts to resume from
    where the previous download left off using HTTP Range requests.

    Parameters
    ----------
    url : str
        URL to download.
    output : str
        Output file path.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    timeout : int
        Request timeout in seconds.
    chunk_size : int
        Chunk size in bytes.
    title : str
        Title for progress display.

    Returns
    -------
    str
        Path to the downloaded file.
    """
    import sys

    # Build opener
    handlers = []
    if cookies_file:
        cj = http.cookiejar.MozillaCookieJar()
        cj.load(cookies_file, ignore_discard=True, ignore_expires=True)
        handlers.append(urllib.request.HTTPCookieProcessor(cj))
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Referer": "https://www.youtube.com/",
        "Origin": "https://www.youtube.com",
        "Connection": "keep-alive",
    }

    # Check if file exists and get current size
    existing_size = 0
    if os.path.isfile(output):
        existing_size = os.path.getsize(output)

    # Open file in append mode
    f = open(output, "ab")

    try:
        # If we have existing data, use Range header
        if existing_size > 0:
            headers["Range"] = f"bytes={existing_size}-"
            req = urllib.request.Request(url, headers=headers)
            try:
                resp = opener.open(req, timeout=timeout)
                total_size = existing_size + int(resp.headers.get("Content-Length", 0))
                # Resume from where we left off
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    existing_size += len(chunk)
                    _show_progress(existing_size, total_size, title)
                resp.close()
            except urllib.error.HTTPError as e:
                if e.code == 416:  # Range Not Satisfiable - file is complete
                    pass
                elif e.code == 429:
                    raise
                else:
                    # Server doesn't support resume, start over
                    f.close()
                    f = open(output, "wb")
                    req = urllib.request.Request(url, headers=headers)
                    resp = opener.open(req, timeout=timeout)
                    total_size = int(resp.headers.get("Content-Length", 0))
                    downloaded = 0
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        _show_progress(downloaded, total_size, title)
                    resp.close()
        else:
            # Fresh download
            req = urllib.request.Request(url, headers=headers)
            resp = opener.open(req, timeout=timeout)
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                _show_progress(downloaded, total_size, title)
            resp.close()

        print()  # New line after progress
        return output

    finally:
        f.close()


def _show_progress(downloaded: int, total: int, title: str = ""):
    """Show download progress on one line."""
    import sys

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


def get_file_size(url: str, cookies_file: str | None = None,
                  proxy: str | None = None, timeout: int = 30) -> int:
    """Get file size without downloading."""
    handlers = []
    if cookies_file:
        cj = http.cookiejar.MozillaCookieJar()
        cj.load(cookies_file, ignore_discard=True, ignore_expires=True)
        handlers.append(urllib.request.HTTPCookieProcessor(cj))
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Referer": "https://www.youtube.com/",
    }

    req = urllib.request.Request(url, headers=headers)
    resp = opener.open(req, timeout=timeout)
    size = int(resp.headers.get("Content-Length", 0) or 0)
    resp.close()
    return size
