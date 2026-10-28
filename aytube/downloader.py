"""
aytube.downloader - Chunked downloads, range-resumption, ffmpeg muxing, and batching.
"""

from __future__ import annotations

import http.cookiejar
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .stream import StreamResult
from .utils import build_opener, find_cookies_path, safe_filename, show_progress

_STREAM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": "video/webm,video/mp4,video/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Referer": "https://www.youtube.com/",
    "Origin": "https://www.youtube.com",
    "Sec-Fetch-Dest": "video",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
}


def get_file_size(path: str) -> int:
    """Return file size in bytes if file exists, else 0."""
    return os.path.getsize(path) if os.path.isfile(path) else 0


def download(
    url_or_result: str | StreamResult,
    output: str | None = None,
    cookies_file: str | None = None,
    proxy: str | None = None,
    quality: str = "best",
    audio_only: bool = False,
    resume: bool = True,
    timeout: int = 60,
    quiet: bool = False,
) -> str:
    """
    Download a YouTube video or stream directly to disk.

    If video resolution is video-only (1080p, 1440p, 4K), automatically muxes
    with highest available audio track using ffmpeg.
    """
    from .extractor import get_stream_url

    if isinstance(url_or_result, StreamResult):
        result = url_or_result
        target_url = result.url
    else:
        result = get_stream_url(
            url_or_result,
            cookies_file=cookies_file,
            proxy=proxy,
            quality=quality,
            audio_only=audio_only,
            verify=False,
            timeout=timeout,
        )
        target_url = result.url

    if not output:
        name = safe_filename(result.title or result.video_id)
        ext = "m4a" if audio_only else (result.container or "mp4")
        output = f"{name}.{ext}"

    # Check if this is a video-only format that needs audio muxing
    if not audio_only and not result.audio_codec and shutil.which("ffmpeg"):
        return _download_and_mux(result, output, cookies_file, proxy, timeout, quiet)

    if resume:
        return download_with_resume(
            target_url,
            output,
            cookies_file=cookies_file,
            proxy=proxy,
            timeout=timeout,
            title=result.title if not quiet else "",
            quiet=quiet,
        )

    return _download_file(
        target_url,
        output,
        cookies_file=cookies_file,
        proxy=proxy,
        timeout=timeout,
        size=result.size,
        title=result.title if not quiet else "",
        quiet=quiet,
    )


def download_with_resume(
    url: str,
    output: str,
    cookies_file: str | None = None,
    proxy: str | None = None,
    timeout: int = 60,
    chunk_size: int = 1048576,  # 1 MB
    title: str = "",
    quiet: bool = False,
) -> str:
    """
    Download with HTTP Range header continuation for interrupted transfers.
    """
    cf = find_cookies_path(cookies_file)
    opener = build_opener(cf, proxy)

    headers = dict(_STREAM_HEADERS)
    if cf and os.path.isfile(cf):
        try:
            cj = http.cookiejar.MozillaCookieJar()
            cj.load(cf, ignore_discard=True, ignore_expires=True)
            pairs = [f"{c.name}={c.value}" for c in cj if c.value]
            if pairs:
                headers["Cookie"] = "; ".join(pairs)
        except Exception:
            pass

    existing_size = get_file_size(output)
    mode = "ab" if existing_size > 0 else "wb"

    if existing_size > 0:
        headers["Range"] = f"bytes={existing_size}-"

    req = urllib.request.Request(url, headers=headers)
    try:
        resp = opener.open(req, timeout=timeout)
        content_len = int(resp.headers.get("Content-Length", 0))
        total_size = existing_size + content_len

        with open(output, mode) as f:
            downloaded = existing_size
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if not quiet:
                    show_progress(downloaded, total_size, title)
        resp.close()
    except urllib.error.HTTPError as exc:
        if exc.code == 416:
            # File already fully completed
            if not quiet:
                print(f"  File is already complete: {output}")
            return output
        raise

    if not quiet:
        sys.stdout.write("\n")
        sys.stdout.flush()

    return output


def _download_file(
    url: str,
    output: str,
    cookies_file: str | None,
    proxy: str | None,
    timeout: int,
    size: int = 0,
    title: str = "",
    quiet: bool = False,
) -> str:
    cf = find_cookies_path(cookies_file)
    opener = build_opener(cf, proxy)
    headers = dict(_STREAM_HEADERS)

    if cf and os.path.isfile(cf):
        try:
            cj = http.cookiejar.MozillaCookieJar()
            cj.load(cf, ignore_discard=True, ignore_expires=True)
            pairs = [f"{c.name}={c.value}" for c in cj if c.value]
            if pairs:
                headers["Cookie"] = "; ".join(pairs)
        except Exception:
            pass

    req = urllib.request.Request(url, headers=headers)
    resp = opener.open(req, timeout=timeout)
    total_size = int(resp.headers.get("Content-Length", size or 0))

    with open(output, "wb") as f:
        downloaded = 0
        chunk_size = 1048576
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if not quiet:
                show_progress(downloaded, total_size, title)
    resp.close()

    if not quiet:
        sys.stdout.write("\n")
        sys.stdout.flush()

    return output


def _download_and_mux(
    result: StreamResult,
    output: str,
    cookies_file: str | None,
    proxy: str | None,
    timeout: int,
    quiet: bool = False,
) -> str:
    """Download video and audio streams independently, then mux using ffmpeg."""
    from .extractor import get_stream_url

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to mux separate video and audio streams.")

    if not quiet:
        print(f"Resolving accompanying high-bitrate audio stream...")

    audio_res = get_stream_url(
        f"https://www.youtube.com/watch?v={result.video_id}",
        cookies_file=cookies_file,
        proxy=proxy,
        audio_only=True,
        quality="high",
        verify=False,
        timeout=timeout,
    )

    tmp_dir = tempfile.mkdtemp(prefix="aytube_mux_")
    v_tmp = os.path.join(tmp_dir, f"video.{result.container or 'mp4'}")
    a_tmp = os.path.join(tmp_dir, f"audio.{audio_res.container or 'm4a'}")

    try:
        if not quiet:
            print(f"Downloading video ({result.quality})...")
        download_with_resume(result.url, v_tmp, cookies_file, proxy, timeout, title="Video", quiet=quiet)

        if not quiet:
            print(f"Downloading audio ({audio_res.quality})...")
        download_with_resume(audio_res.url, a_tmp, cookies_file, proxy, timeout, title="Audio", quiet=quiet)

        if not quiet:
            print(f"Muxing streams into {output}...")

        cmd = [
            "ffmpeg", "-y", "-i", v_tmp, "-i", a_tmp,
            "-c", "copy", "-movflags", "+faststart",
            output,
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg muxing failed: {proc.stderr.decode(errors='replace')[:200]}")
    finally:
        for p in (v_tmp, a_tmp):
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass

    return output


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
    Download multiple YouTube videos sequentially or concurrently.
    """
    url_list: list[str] = []
    if isinstance(urls, str):
        if os.path.isfile(urls):
            with open(urls, "r", encoding="utf-8") as f:
                url_list = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        elif "\n" in urls:
            url_list = [l.strip() for l in urls.split("\n") if l.strip() and not l.startswith("#")]
        else:
            url_list = [urls.strip()]
    else:
        url_list = list(urls)

    if not url_list:
        return []

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    results: list[tuple[str, bool, Any]] = []

    def download_one(target_url: str) -> tuple[str, bool, Any]:
        try:
            from .extractor import get_stream_url
            r = get_stream_url(target_url, cookies_file=cookies_file, proxy=proxy, quality=quality or "best", audio_only=audio_only)
            ext = "m4a" if audio_only else (r.container or "mp4")
            dest = os.path.join(output_dir, f"{safe_filename(r.title or r.video_id)}.{ext}") if output_dir else None
            path = download(r, output=dest, cookies_file=cookies_file, proxy=proxy, quality=quality or "best", audio_only=audio_only)
            return (target_url, True, path)
        except Exception as e:
            return (target_url, False, str(e))

    if concurrent <= 1:
        for i, u in enumerate(url_list, 1):
            print(f"\n[{i}/{len(url_list)}] Processing: {u}")
            res = download_one(u)
            results.append(res)
            if res[1]:
                print(f"  OK: {res[2]}")
            else:
                print(f"  FAILED: {res[2]}")
            if i < len(url_list):
                time.sleep(2)
        return results

    # Concurrent multithreaded download
    with ThreadPoolExecutor(max_workers=concurrent) as executor:
        future_to_url = {executor.submit(download_one, u): u for u in url_list}
        for future in as_completed(future_to_url):
            results.append(future.result())

    return results
