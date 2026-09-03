#!/usr/bin/env python3
"""
aytube — YouTube stream extractor

Usage:
    aytube "URL"                        # download best
    aytube list "URL"                   # list formats
    aytube download "URL" -q 1080p      # download specific quality
    aytube get "URL" -q 720p            # get stream URL
    aytube search "query"                # search YouTube
    aytube info "URL"                    # video metadata
    aytube subs "URL"                    # list subtitles
    aytube thumb "ID" -o out.jpg         # download thumbnail
    aytube chapters "URL"                # show chapters
    aytube related "URL"                 # related videos
    aytube batch urls.txt                # batch download
"""
import argparse
import json
import os
import sys


def _is_url(s: str) -> bool:
    if not s:
        return False
    return (s.startswith(('http://', 'https://'))
            or 'youtube.com' in s
            or 'youtu.be' in s
            or len(s) == 11)


def build_parser():
    p = argparse.ArgumentParser(
        prog='aytube',
        description='aytube — YouTube stream extractor',
    )

    # Optional subcommand as FIRST positional
    p.add_argument('command', nargs='?', default=None,
                   help='Command: get/list/download/info/subs/search/thumb/chapters/related/batch/resume/setup/show')

    # Everything else is a flag
    p.add_argument('url', nargs='?', default=None, help='YouTube URL / video ID / search query / file path')
    p.add_argument('-q', '--quality', default='best', help='Quality: best/1080p/720p/480p/360p/audio')
    p.add_argument('-a', '--audio', action='store_true', help='Audio only')
    p.add_argument('-o', '--output', help='Output file/directory path')
    p.add_argument('-c', '--cookies', help='Cookies file (Netscape format)')
    p.add_argument('-p', '--proxy', help='HTTP/HTTPS proxy URL')
    p.add_argument('-f', '--format', type=int, help='Force specific itag (137, 251, etc.)')
    p.add_argument('-j', '--json', action='store_true', help='JSON output')
    p.add_argument('-v', '--verbose', action='store_true')
    p.add_argument('--quiet', action='store_true')
    p.add_argument('-n', '--concurrent', type=int, default=1, help='Concurrent downloads')
    p.add_argument('-N', '--max-results', type=int, default=20, help='Max results for search/related')
    return p


def _q(args):
    return str(args.format) if args.format else args.quality


def main():
    p = build_parser()
    args = p.parse_args()

    cmd = args.command
    url = args.url

    # If no command given, decide from url
    if not cmd:
        if url and _is_url(url):
            cmd = 'download'
        elif url:
            cmd = 'search'
        else:
            p.print_help()
            sys.exit(0)

    # Auto search if download got a non-URL
    if cmd == 'download' and url and not _is_url(url):
        cmd = 'search'

    try:
        if cmd == 'get':
            _get(url, args)
        elif cmd == 'list':
            _list(url, args)
        elif cmd == 'download':
            _download(url, args)
        elif cmd == 'info':
            _info(url, args)
        elif cmd == 'subs':
            _subs(url, args)
        elif cmd == 'search':
            _search(url, args)
        elif cmd == 'thumb':
            _thumb(url, args)
        elif cmd == 'chapters':
            _chapters(url, args)
        elif cmd == 'related':
            _related(url, args)
        elif cmd == 'batch':
            _batch(url, args)
        elif cmd == 'resume':
            _resume(url, args)
        elif cmd == 'setup':
            from aytube import setup_wizard
            setup_wizard()
        elif cmd == 'show':
            from aytube import show_config
            show_config()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# ── handlers ────────────────────────────────────────────────────────────────

def _get(url, args):
    from aytube import get_stream_url
    r = get_stream_url(url, cookies_file=args.cookies, proxy=args.proxy,
                       quality=_q(args), audio_only=args.audio)
    if args.json:
        print(json.dumps(r._asdict(), indent=2, ensure_ascii=False, default=str))
    else:
        print(r.url)


def _list(url, args):
    from aytube import list_formats
    formats = list_formats(url, cookies_file=args.cookies, proxy=args.proxy,
                           audio_only=args.audio)
    if not formats:
        print("No formats found.")
        return
    if args.json:
        print(json.dumps(formats, indent=2, ensure_ascii=False))
        return
    print(f"{'#':>3}  {'ITAG':>5}  {'RES':>8}  {'FPS':>4}  {'SIZE':>10}  {'CODEC'}")
    print("─" * 60)
    for i, f in enumerate(formats, 1):
        res = f.get('quality') or f.get('resolution') or 'audio'
        fps = str(f.get('fps') or '-')
        size = f"{f['size']/1024/1024:.1f}M" if f.get('size') else "?"
        codec = (f.get('video_codec') or f.get('audio_codec') or '?').split('.')[0]
        flag = ""
        if f.get('is_video_only'):
            flag += " ↑"
        if f.get('is_hdr'):
            flag += " HDR"
        print(f"{i:>3}  {f['itag']:>5}  {res:>8}  {fps:>4}  {size:>10}  {codec}{flag}")


def _download(url, args):
    from aytube import download
    if not args.quiet:
        print(f"↓ {url}")
        print(f"  {_q(args)}")
    path = download(url, output=args.output, cookies_file=args.cookies,
                    proxy=args.proxy, quality=_q(args), audio_only=args.audio)
    if not args.quiet:
        print(f"✓ {path}")


def _resume(url, args):
    from aytube import download_with_resume, get_stream_url
    r = get_stream_url(url, cookies_file=args.cookies, proxy=args.proxy)
    path = download_with_resume(r.url, output=args.output, cookies_file=args.cookies,
                                proxy=args.proxy, title=r.title)
    if not args.quiet:
        print(f"✓ {path}")


def _info(url, args):
    from aytube import get_metadata
    meta = get_metadata(url, cookies_file=args.cookies, proxy=args.proxy)
    if args.json:
        print(json.dumps(meta, indent=2, ensure_ascii=False, default=str))
        return
    print(f"Title:     {meta.get('title', 'N/A')}")
    print(f"Channel:   {meta.get('channel_name', 'N/A')}")
    print(f"Duration:  {meta.get('duration', 'N/A')}")
    print(f"Views:     {meta.get('view_count', 0):,}")
    print(f"Date:      {meta.get('upload_date', 'N/A')}")
    print(f"Thumb:     {meta.get('thumbnail', 'N/A')}")


def _subs(url, args):
    from aytube import list_subtitles
    subs = list_subtitles(url, cookies_file=args.cookies, proxy=args.proxy)
    if not subs:
        print("No subtitles.")
        return
    if args.json:
        print(json.dumps(subs, indent=2, ensure_ascii=False))
        return
    for lang, tracks in subs.items():
        for t in tracks:
            a = " [auto]" if t['is_auto'] else ""
            print(f"  {lang}: {t['lang_name']}{a}")


def _search(query, args):
    from aytube import search
    results = search(query, cookies_file=args.cookies, proxy=args.proxy,
                     max_results=args.max_results)
    if not results:
        print("No results.")
        return
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    print(f"Search: {query}\n")
    for i, v in enumerate(results, 1):
        print(f"{i:>3}. {v['title']}")
        print(f"     {v['url']}")
        if v.get('duration'):
            print(f"     {v['duration']}")


def _thumb(video_id, args):
    from aytube import download_thumbnail
    path = download_thumbnail(video_id, output=args.output, cookies_file=args.cookies,
                              proxy=args.proxy)
    if not args.quiet:
        print(f"✓ {path}")


def _chapters(url, args):
    from aytube import get_chapters
    chapters = get_chapters(url, cookies_file=args.cookies, proxy=args.proxy)
    if not chapters:
        print("No chapters.")
        return
    if args.json:
        print(json.dumps(chapters, indent=2, ensure_ascii=False))
        return
    for ch in chapters:
        print(f"  {ch['start_time_formatted']}  {ch['title']}")


def _related(url, args):
    from aytube import get_related_videos
    videos = get_related_videos(url, cookies_file=args.cookies, proxy=args.proxy,
                                max_results=args.max_results)
    if not videos:
        print("No related videos.")
        return
    if args.json:
        print(json.dumps(videos, indent=2, ensure_ascii=False))
        return
    for i, v in enumerate(videos, 1):
        print(f"{i:>3}. {v['title']}")
        print(f"     {v['url']}")


def _batch(filepath, args):
    from aytube import batch_download
    if not filepath or not os.path.isfile(filepath):
        print("Provide a file with URLs for batch mode.")
        sys.exit(1)
    with open(filepath) as fh:
        urls = [l.strip() for l in fh if l.strip() and not l.startswith('#')]
    print(f"Batch: {len(urls)} videos")
    results = batch_download(urls, quality=_q(args), audio_only=args.audio,
                             cookies_file=args.cookies, proxy=args.proxy,
                             output_dir=args.output or '.', concurrent=args.concurrent)
    ok = sum(1 for _, s, _ in results if s)
    print(f"Done: {ok}/{len(results)}")


if __name__ == '__main__':
    main()
