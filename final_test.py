#!/usr/bin/env python3
"""Full test battery for aytube v2.0.0"""
import sys
import time
from aytube import (
    get_stream_url, list_formats, get_metadata,
    search, extract_video_id, download
)

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
PASS = 0
FAIL = 0
DELAY = 4  # seconds between network tests to avoid rate limiting

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {name}")
        PASS += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        FAIL += 1


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# 1. extract_video_id
section("1. extract_video_id")
check("watch URL", extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ")
check("youtu.be URL", extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ")
check("shorts URL", extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ")
check("embed URL", extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ")
check("with timestamp", extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30") == "dQw4w9WgXcQ")


# 2. get_metadata
section("2. get_metadata")
try:
    meta = get_metadata(URL)
    check("title exists", bool(meta.get("title")), f"got: {meta.get('title','')[:30]}")
    check("channel exists", bool(meta.get("channel_name")), f"got: {meta.get('channel_name','')}")
    check("duration > 0", meta.get("duration_seconds", 0) > 0, f"got: {meta.get('duration')}")
    check("view_count > 0", meta.get("view_count", 0) > 0, f"got: {meta.get('view_count')}")
    check("thumbnail URL", meta.get("thumbnail", "").startswith("http"), f"got: {meta.get('thumbnail','')[:40]}")
except Exception as e:
    check("get_metadata works", False, str(e))


# 3. list_formats
section("3. list_formats")
try:
    formats = list_formats(URL)
    check("formats returned", len(formats) > 0, f"got {len(formats)}")
    if formats:
        # Check quality labels are correct (not all "audio")
        video_fmts = [f for f in formats if not f.get("mime_type", "").startswith("audio")]
        check("video formats exist", len(video_fmts) > 0, f"video: {len(video_fmts)}, total: {len(formats)}")
        # Check URLs are present
        with_url = [f for f in formats if f.get("url")]
        check("URLs resolved", len(with_url) > 0, f"{len(with_url)}/{len(formats)} have URLs")
        # Check itags are diverse
        itags = sorted(set(f.get("itag", 0) for f in formats))
        check("diverse itags", len(itags) > 5, f"itags: {itags[:10]}")
        print(f"\n  Sample formats:")
        for f in formats[:5]:
            print(f"    itag={f['itag']} q={f['quality']} size={f['size']} url={f.get('url','')[:50]}")
except Exception as e:
    check("list_formats works", False, str(e))


# 4. get_stream_url - quality selection
section("4. get_stream_url quality selection")
qualities = ["1080p", "720p", "480p", "360p", "best"]
for q in qualities:
    try:
        r = get_stream_url(URL, quality=q)
        check(f"quality={q}", bool(r.url), f"got: {r.quality} itag={r.itag}")
        time.sleep(DELAY)
    except Exception as e:
        check(f"quality={q}", False, str(e)[:60])


# 5. get_stream_url - audio only
section("5. get_stream_url audio_only")
try:
    r = get_stream_url(URL, audio_only=True)
    check("audio_only has URL", bool(r.url), f"got: {r.quality} itag={r.itag}")
    check("audio_only codec", bool(r.audio_codec), f"got: {r.audio_codec}")
except Exception as e:
    check("audio_only works", False, str(e)[:60])


# 6. get_stream_url - specific itag
section("6. get_stream_url specific itag")
try:
    r = get_stream_url(URL, quality="251")
    check("itag=251 works", r.itag == 251, f"got itag={r.itag}")
except Exception as e:
    check("itag=251 works", False, str(e)[:60])


# 7. search
section("7. search")
try:
    results = search("lofi hip hop", max_results=5)
    check("search returns results", len(results) > 0, f"got {len(results)}")
    if results:
        check("result has title", bool(results[0].get("title")), f"got: {results[0].get('title','')[:30]}")
        check("result has URL", bool(results[0].get("url")), f"got: {results[0].get('url','')[:50]}")
        check("result has video_id", bool(results[0].get("video_id")), f"got: {results[0].get('video_id','')}")
except Exception as e:
    check("search works", False, str(e)[:60])


# 8. StreamResult fields
section("8. StreamResult fields")
try:
    r = get_stream_url(URL, quality="720p")
    check("url field", bool(r.url), f"len={len(r.url)}")
    check("quality field", bool(r.quality), f"got: {r.quality}")
    check("container field", r.container in ("mp4", "webm"), f"got: {r.container}")
    check("size field", r.size > 0, f"got: {r.size}")
    check("title field", bool(r.title), f"got: {r.title[:30]}")
    check("video_id field", r.video_id == "dQw4w9WgXcQ", f"got: {r.video_id}")
    check("itag field", r.itag > 0, f"got: {r.itag}")
except Exception as e:
    check("StreamResult fields", False, str(e)[:60])


# Summary
section("SUMMARY")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  TOTAL: {PASS + FAIL}")
if FAIL == 0:
    print("\n  ALL TESTS PASSED!")
else:
    print(f"\n  {FAIL} tests failed")
    sys.exit(1)
