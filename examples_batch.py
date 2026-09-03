#!/usr/bin/env python3
"""
aytube - Batch Download Example

Download multiple videos or extract streams in bulk.
"""

from aytube import get_stream_url, extract_video_id


def batch_video(urls, quality="720p", cookies_file=None):
    """Extract streams for multiple videos."""
    results = []
    for url in urls:
        try:
            r = get_stream_url(url, quality=quality, cookies_file=cookies_file)
            results.append({
                "video_id": r.video_id,
                "title": r.title,
                "quality": r.quality,
                "size": r.size,
                "container": r.container,
                "url": r.url,
                "error": None,
            })
            print(f"  OK: {r.title[:50]:50s} | {r.size:>12,} bytes")
        except Exception as e:
            results.append({"video_id": extract_video_id(url), "title": "", "error": str(e)})
            print(f"  FAIL: {url[:50]:50s} | {e}")
    return results


def batch_audio(urls, quality="high", cookies_file=None):
    """Extract audio-only streams for multiple videos."""
    results = []
    for url in urls:
        try:
            r = get_stream_url(url, audio_only=True, quality=quality, cookies_file=cookies_file)
            results.append({
                "video_id": r.video_id,
                "title": r.title,
                "quality": r.quality,
                "size": r.size,
                "codec": r.audio_codec,
                "url": r.url,
                "error": None,
            })
            print(f"  OK: {r.title[:50]:50s} | {r.size:>12,} bytes | {r.audio_codec}")
        except Exception as e:
            results.append({"video_id": extract_video_id(url), "title": "", "error": str(e)})
            print(f"  FAIL: {url[:50]:50s} | {e}")
    return results


if __name__ == "__main__":
    video_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=9bZkp7q19f0",
        "https://www.youtube.com/watch?v=kJQP7kiw5Fk",
    ]

    print("=== Batch Video Extraction (720p) ===")
    batch_video(video_urls, quality="720p")

    print("\n=== Batch Audio Extraction (high) ===")
    batch_audio(video_urls, quality="high")
