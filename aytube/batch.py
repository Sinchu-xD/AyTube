"""
Batch download support for aytube.

Allows downloading multiple videos from a list of URLs or a file.
Supports sequential and concurrent downloads.
"""
from __future__ import annotations

import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def _safe_filename(name: str, max_len: int = 100) -> str:
    """Sanitize a string for use as a filename."""
    import re
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "download"


def batch_download(
    urls: list[str] | str,
    quality: str | None = None,
    audio_only: bool = False,
    cookies_file: str | None = None,
    proxy: str | None = None,
    output_dir: str | None = None,
    concurrent: int = 1,
) -> list[tuple[str, bool, Any]]:
    """
    Download multiple YouTube videos.

    Parameters
    ----------
    urls : list[str] | str
        List of YouTube URLs, or path to a file with one URL per line.
    quality : str | None
        Preferred quality for all videos.
    audio_only : bool
        If True, download audio only.
    cookies_file : str | None
        Path to cookies_file file.
    proxy : str | None
        HTTP/HTTPS proxy URL.
    output_dir : str | None
        Directory to save files. Defaults to current directory.
    concurrent : int
        Number of concurrent downloads (1 = sequential).

    Returns
    -------
    list[tuple[str, bool, Any]]
        List of (url, success, path_or_error) tuples.
    """
    # Parse input
    if isinstance(urls, str):
        if os.path.isfile(urls):
            with open(urls, 'r') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        elif '\n' in urls:
            urls = [line.strip() for line in urls.split('\n') if line.strip() and not line.startswith('#')]
        else:
            urls = [urls]

    if not urls:
        return []

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    if concurrent <= 1:
        return _download_sequential(urls, quality, audio_only, cookies_file, proxy, output_dir)
    else:
        return _download_concurrent(urls, quality, audio_only, cookies_file, proxy, output_dir, concurrent)


def _download_sequential(urls, quality, audio_only, cookies_file, proxy, output_dir):
    """Download videos one at a time."""
    results = []
    total = len(urls)
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{total}] {url}")
        try:
            path = _download_single(url, quality, audio_only, cookies_file, proxy, output_dir)
            results.append((url, True, path))
            print(f"  OK: {path}")
        except Exception as e:
            results.append((url, False, str(e)))
            print(f"  FAIL: {e}")
        if i < total:
            time.sleep(5)
    return results


def _download_concurrent(urls, quality, audio_only, cookies_file, proxy, output_dir, max_workers):
    """Download videos concurrently using threads."""
    results = []
    results_lock = threading.Lock()
    completed = [0]
    total = len(urls)

    def download_one(url):
        try:
            path = _download_single(url, quality, audio_only, cookies_file, proxy, output_dir)
            with results_lock:
                completed[0] += 1
                print(f"\n[{completed[0]}/{total}] OK: {url}")
            return (url, True, path)
        except Exception as e:
            with results_lock:
                completed[0] += 1
                print(f"\n[{completed[0]}/{total}] FAIL: {url} - {e}")
            return (url, False, str(e))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_one, url) for url in urls]
        for future in as_completed(futures):
            results.append(future.result())

    return results


def _download_single(url, quality, audio_only, cookies_file, proxy, output_dir):
    """Download a single video."""
    from aytube import download, get_stream_url

    r = get_stream_url(
        url, cookies_file=cookies_file, proxy=proxy,
        quality=quality, audio_only=audio_only, verify=False,
    )

    if output_dir:
        safe_title = _safe_filename(r.title or r.video_id)
        ext = "m4a" if audio_only else r.container or "mp4"
        output = os.path.join(output_dir, f"{safe_title}.{ext}")
    else:
        output = None

    return download(
        url, output=output, cookies_file=cookies_file, proxy=proxy,
        quality=quality, audio_only=audio_only,
    )
