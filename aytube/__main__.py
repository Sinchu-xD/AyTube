#!/usr/bin/env python3
"""
aytube CLI — Command-line interface for YouTube stream extraction and downloading.

Usage:
    aytube "URL"                        # download best quality
    aytube list "URL"                   # list available formats
    aytube get "URL" -q 1080p           # get direct stream URL
    aytube download "URL" -a            # download audio only
    aytube info "URL"                   # show video metadata
    aytube subs "URL"                   # list subtitles
    aytube search "query"               # search YouTube
    aytube thumb "URL" -o thumb.jpg     # download thumbnail
    aytube chapters "URL"               # list chapters
    aytube related "URL"                # list related videos
    aytube batch urls.txt               # batch download from file
    aytube setup                        # configure default settings
    aytube show                         # print current configuration
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys

from aytube import (
    batch_download,
    download,
    download_thumbnail,
    download_with_resume,
    extract_video_id,
    get_chapters,
    get_metadata,
    get_related_videos,
    get_stream_url,
    list_formats,
    list_subtitles,
    search,
    setup_wizard,
    show_config,
)


def _is_url(s: str) -> bool:
    if not s:
        return False
    return (
        s.startswith(("http://", "https://"))
        or "youtube.com" in s
        or "youtu.be" in s
        or (len(s) == 11 and not s.startswith("-"))
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aytube",
        description="aytube — High-performance YouTube stream extractor and downloader",
    )
    p.add_argument(
        "command",
        nargs="?",
        default=None,
        help="Command: get | list | download | info | subs | search | thumb | chapters | related | batch | resume | setup | show",
    )
    p.add_argument("url", nargs="?", default=None, help="YouTube URL / Video ID / Search query / File path")
    p.add_argument("-q", "--quality", default="best", help="Quality: best | 1080p | 720p | 480p | 360p | high | low")
    p.add_argument("-a", "--audio", action="store_true", help="Audio-only extraction")
    p.add_argument("-o", "--output", help="Output file or directory path")
    p.add_argument("-c", "--cookies", help="Path to Netscape-format cookies.txt file")
    p.add_argument("-p", "--proxy", help="HTTP / HTTPS proxy URL")
    p.add_argument("-f", "--format", type=int, help="Target specific itag (e.g. 137, 251)")
    p.add_argument("-j", "--json", action="store_true", help="Output structured JSON")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose error tracebacks")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    p.add_argument("-n", "--concurrent", type=int, default=1, help="Concurrent workers for batch download")
    p.add_argument("-N", "--max-results", type=int, default=20, help="Max results for search or related queries")
    return p


def _target_quality(args: argparse.Namespace) -> str:
    return str(args.format) if args.format else args.quality


def main():
    parser = build_parser()
    args = parser.parse_args()

    cmd = args.command
    url = args.url

    # Intelligent dispatch when command is omitted
    if not cmd:
        if url and _is_url(url):
            cmd = "download"
        elif url:
            cmd = "search"
        else:
            parser.print_help()
            sys.exit(0)

    if cmd == "download" and url and not _is_url(url):
        cmd = "search"

    try:
        if cmd == "get":
            _handle_get(url, args)
        elif cmd == "list":
            _handle_list(url, args)
        elif cmd == "download":
            _handle_download(url, args)
        elif cmd == "info":
            _handle_info(url, args)
        elif cmd == "subs":
            _handle_subs(url, args)
        elif cmd == "search":
            _handle_search(url, args)
        elif cmd == "thumb":
            _handle_thumb(url, args)
        elif cmd == "chapters":
            _handle_chapters(url, args)
        elif cmd == "related":
            _handle_related(url, args)
        elif cmd == "batch":
            _handle_batch(url, args)
        elif cmd == "resume":
            _handle_resume(url, args)
        elif cmd == "setup":
            setup_wizard()
        elif cmd == "show":
            show_config()
        else:
            # Fallback if first arg was a URL
            if _is_url(cmd):
                args.url = cmd
                _handle_download(cmd, args)
            else:
                parser.print_help()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _handle_get(url: str, args: argparse.Namespace):
    res = get_stream_url(
        url,
        cookies_file=args.cookies,
        proxy=args.proxy,
        quality=_target_quality(args),
        audio_only=args.audio,
    )
    if args.json:
        print(json.dumps(dataclasses.asdict(res), indent=2, ensure_ascii=False, default=str))
    else:
        print(res.url)


def _handle_list(url: str, args: argparse.Namespace):
    fmts = list_formats(
        url,
        cookies_file=args.cookies,
        proxy=args.proxy,
        audio_only=args.audio,
    )
    if not fmts:
        print("No formats found.")
        return

    if args.json:
        print(json.dumps(fmts, indent=2, ensure_ascii=False))
        return

    print(f"{'#':>3}  {'ITAG':>5}  {'RES':>8}  {'FPS':>4}  {'SIZE':>10}  {'CODEC'}")
    print("─" * 60)
    for i, f in enumerate(fmts, 1):
        res = f.get("quality") or f.get("resolution") or "audio"
        fps = str(f.get("fps") or "-")
        size = f"{f['size'] / 1024 / 1024:.1f}M" if f.get("size") else "?"
        codec = (f.get("video_codec") or f.get("audio_codec") or "?").split(".")[0]
        flag = " [video-only]" if f.get("is_video_only") else ""
        if f.get("is_hdr"):
            flag += " [HDR]"
        print(f"{i:>3}  {f['itag']:>5}  {res:>8}  {fps:>4}  {size:>10}  {codec}{flag}")


def _handle_download(url: str, args: argparse.Namespace):
    if not args.quiet:
        print(f"↓ Fetching {url} ({_target_quality(args)})...")
    path = download(
        url,
        output=args.output,
        cookies_file=args.cookies,
        proxy=args.proxy,
        quality=_target_quality(args),
        audio_only=args.audio,
        quiet=args.quiet,
    )
    if not args.quiet:
        print(f"✓ Saved to: {path}")


def _handle_resume(url: str, args: argparse.Namespace):
    res = get_stream_url(url, cookies_file=args.cookies, proxy=args.proxy)
    out = args.output or f"{res.title or res.video_id}.{res.container or 'mp4'}"
    path = download_with_resume(
        res.url,
        output=out,
        cookies_file=args.cookies,
        proxy=args.proxy,
        title=res.title,
        quiet=args.quiet,
    )
    if not args.quiet:
        print(f"✓ Saved to: {path}")


def _handle_info(url: str, args: argparse.Namespace):
    meta = get_metadata(url, cookies_file=args.cookies, proxy=args.proxy)
    if args.json:
        print(json.dumps(meta, indent=2, ensure_ascii=False, default=str))
        return
    print(f"Title:     {meta.get('title', 'N/A')}")
    print(f"Channel:   {meta.get('channel_name', 'N/A')}")
    print(f"Duration:  {meta.get('duration', 'N/A')}")
    print(f"Views:     {meta.get('view_count', 0):,}")
    print(f"Date:      {meta.get('upload_date', 'N/A')}")
    print(f"Thumbnail: {meta.get('thumbnail', 'N/A')}")


def _handle_subs(url: str, args: argparse.Namespace):
    subs = list_subtitles(url, cookies_file=args.cookies, proxy=args.proxy)
    if not subs:
        print("No subtitles found.")
        return
    if args.json:
        print(json.dumps(subs, indent=2, ensure_ascii=False))
        return
    for lang, tracks in subs.items():
        for t in tracks:
            auto = " [auto]" if t.get("is_auto") else ""
            print(f"  {lang}: {t.get('lang_name', '')}{auto}")


def _handle_search(query: str, args: argparse.Namespace):
    results = search(query, cookies_file=args.cookies, proxy=args.proxy, max_results=args.max_results)
    if not results:
        print("No results found.")
        return
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    print(f"Results for '{query}':\n")
    for i, v in enumerate(results, 1):
        dur = f" ({v['duration']})" if v.get("duration") else ""
        print(f"  {i:>2}. {v['title']}{dur}")
        print(f"      {v['url']}")


def _handle_thumb(url: str, args: argparse.Namespace):
    vid = extract_video_id(url) or url
    path = download_thumbnail(vid, output=args.output, cookies_file=args.cookies, proxy=args.proxy)
    if not args.quiet:
        print(f"✓ Saved thumbnail to: {path}")


def _handle_chapters(url: str, args: argparse.Namespace):
    chaps = get_chapters(url, cookies_file=args.cookies, proxy=args.proxy)
    if not chaps:
        print("No chapters found.")
        return
    if args.json:
        print(json.dumps(chaps, indent=2, ensure_ascii=False))
        return
    for c in chaps:
        print(f"  {c['start_time_formatted']}  {c['title']}")


def _handle_related(url: str, args: argparse.Namespace):
    vid = extract_video_id(url) or url
    rel = get_related_videos(vid, cookies_file=args.cookies, proxy=args.proxy, max_results=args.max_results)
    if not rel:
        print("No related videos found.")
        return
    if args.json:
        print(json.dumps(rel, indent=2, ensure_ascii=False))
        return
    for i, v in enumerate(rel, 1):
        print(f"  {i:>2}. {v['title']}")
        print(f"      {v['url']}")


def _handle_batch(filepath: str, args: argparse.Namespace):
    if not filepath or not os.path.isfile(filepath):
        print("Specify a valid file containing URLs for batch download.", file=sys.stderr)
        sys.exit(1)
    results = batch_download(
        filepath,
        quality=_target_quality(args),
        audio_only=args.audio,
        cookies_file=args.cookies,
        proxy=args.proxy,
        output_dir=args.output or ".",
        concurrent=args.concurrent,
    )
    ok_count = sum(1 for _, ok, _ in results if ok)
    print(f"\nCompleted: {ok_count}/{len(results)} successful.")


if __name__ == "__main__":
    main()
