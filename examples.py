#!/usr/bin/env python3
"""
aytube - Usage Examples

Demonstrates all features of the aytube package:
- Basic stream extraction
- Video quality selection
- Audio-only extraction
- Cookie support (auto-discovery + manual)
- Proxy support
- Multiple URL formats
- Error handling
"""

from aytube import get_stream_url, extract_video_id, StreamResult


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def demo_basic():
    """Basic usage - get the best quality stream."""
    section("1. Basic Usage - Best Quality")

    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    try:
        result = get_stream_url(url)
        print(f"Title:    {result.title}")
        print(f"Video ID: {result.video_id}")
        print(f"Quality:  {result.quality}")
        print(f"Container: {result.container}")
        print(f"Video:    {result.video_codec or 'N/A'}")
        print(f"Audio:    {result.audio_codec or 'N/A (video-only)'}")
        print(f"Size:     {result.size:,} bytes")
        print(f"URL:      {result.url[:80]}...")
    except Exception as e:
        print(f"Error: {e}")


def demo_quality():
    """Different quality levels."""
    section("2. Video Quality Selection")

    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    qualities = ["1080p", "720p", "480p", "360p", "best"]

    for q in qualities:
        try:
            r = get_stream_url(url, quality=q)
            audio = r.audio_codec or "none"
            print(f"  {q:6s} -> {r.quality:6s} | itag={r.itag} | "
                  f"{r.size:>12,} bytes | {r.container} | v={r.video_codec or 'none':20s} | a={audio}")
        except Exception as e:
            print(f"  {q:6s} -> Error: {e}")


def demo_audio():
    """Audio-only extraction."""
    section("3. Audio Only")

    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    qualities = ["high", "medium", "low", "best"]

    for q in qualities:
        try:
            r = get_stream_url(url, audio_only=True, quality=q)
            print(f"  {q:6s} -> {r.quality:6s} | itag={r.itag} | "
                  f"{r.size:>12,} bytes | {r.container} | {r.audio_codec}")
        except Exception as e:
            print(f"  {q:6s} -> Error: {e}")


def demo_url_formats():
    """Different YouTube URL formats."""
    section("4. URL Format Support")

    video_id = "dQw4w9WgXcQ"
    urls = [
        ("watch", f"https://www.youtube.com/watch?v={video_id}"),
        ("youtu.be", f"https://youtu.be/{video_id}"),
        ("shorts", f"https://www.youtube.com/shorts/{video_id}"),
        ("embed", f"https://www.youtube.com/embed/{video_id}"),
    ]

    for name, url in urls:
        try:
            r = get_stream_url(url, quality="720p")
            print(f"  {name:8s} -> {r.quality} | itag={r.itag} | {r.size:>12,} bytes | {r.title[:40]}")
        except Exception as e:
            print(f"  {name:8s} -> Error: {e}")


def demo_extract_id():
    """Video ID extraction from URLs."""
    section("5. extract_video_id()")

    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s",
    ]

    for url in urls:
        vid = extract_video_id(url)
        print(f"  {url[:55]:55s} -> {vid}")


def demo_with_cookies():
    """Using cookies for rate-limited or age-restricted videos."""
    section("6. Cookie Support")

    print("""
  Option 1: Auto-discovery (no code change needed)
  -------------------------------------------------
  Place a cookies_file file in one of these locations:
    - /home/ubuntu/Yt/cookies_file          (same dir as this script)
    - ./cookies_file                         (current working directory)
    - ~/.config/aytube/cookies_file

  aytube will automatically use cookies if YouTube rate-limits (HTTP 429).

  Option 2: Explicit path
  -------------------------------------------------
  result = get_stream_url(
      "https://www.youtube.com/watch?v=VIDEO_ID",
      cookies_file="/path/to/cookies_file",
  )

  Getting cookies_file:
  1. Install "Get cookies.txt LOCALLY" Chrome extension
  2. Log into youtube.com
  3. Click extension -> Export as Netscape format
""")


def demo_with_proxy():
    """Using a proxy."""
    section("7. Proxy Support")

    print("""
  result = get_stream_url(
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      proxy="http://127.0.0.1:8080",
      quality="720p",
  )

  Supported proxy formats:
    - HTTP:  "http://127.0.0.1:8080"
    - HTTPS: "https://127.0.0.1:8080"
    - With auth: "http://user:pass@127.0.0.1:8080"
""")


def demo_error_handling():
    """Common errors and how to handle them."""
    section("8. Error Handling")

    print("""
  from aytube import get_stream_url

  try:
      result = get_stream_url(url, cookies_file="cookies_file")
  except ValueError as e:
      # playabilityStatus errors:
      # - "Age-restricted video. Provide a cookies_file..."
      # - "This live stream is currently offline."
      # - "Video is unplayable: ..."
      # - "Rate-limited by YouTube (HTTP 429)..."
      print(f"Video unavailable: {e}")
  except RuntimeError as e:
      # Cipher extraction failure:
      # - "Could not extract signature decipher function..."
      # - "Could not decipher signature..."
      print(f"Cipher error: {e}")
  except Exception as e:
      # Network errors, timeouts, etc.
      print(f"Unexpected error: {e}")

  Rate limit auto-retry:
  ----------------------
  aytube automatically retries once with auto-discovered cookies
  if you get HTTP 429 and haven't passed cookies_file explicitly.
""")


def demo_stream_result():
    """StreamResult object fields."""
    section("9. StreamResult Object")

    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    r = get_stream_url(url, quality="1080p")

    print(f"""
  result = get_stream_url(url, quality="1080p")

  result.url         # -> "https://rr3---sn-...googlevideo.com/videoplayback?..."
  result.quality     # -> "1080p"
  result.container   # -> "mp4" or "webm"
  result.video_codec # -> "avc1.640028" or "av01.0.12M.08" or "vp9"
  result.audio_codec # -> "mp4a.40.2" or "opus" or "" (video-only)
  result.size        # -> 80911999 (bytes, from contentLength)
  result.title       # -> "Rick Astley - Never Gonna Give You Up..."
  result.video_id    # -> "dQw4w9WgXcQ"
  result.itag        # -> 137 (YouTube format ID)
  result.mime_type   # -> "video/mp4; codecs=\"avc1.640028\""
  result.raw         # -> original format dict from YouTube
""")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                     aytube Examples                         ║
║   Extract direct YouTube stream URLs without yt-dlp/pytube   ║
╚══════════════════════════════════════════════════════════════╝
""")

    demo_basic()
    demo_quality()
    demo_audio()
    demo_url_formats()
    demo_extract_id()
    demo_with_cookies()
    demo_with_proxy()
    demo_error_handling()
    demo_stream_result()

    print(f"\n{'='*60}")
    print("  All examples completed!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
