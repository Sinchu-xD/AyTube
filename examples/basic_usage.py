#!/usr/bin/env python3
"""
Basic stream extraction and inspection example using aytube.
"""

from aytube import get_stream_url, list_formats, extract_video_id


def main():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"Target Video: {url}")
    print(f"Extracted Video ID: {extract_video_id(url)}\n")

    # 1. Best video stream (includes 1080p / 720p with fallback)
    print("1. Extracting best stream...")
    result = get_stream_url(url, quality="best")
    print(f"   Title:     {result.title}")
    print(f"   Quality:   {result.quality}")
    print(f"   Container: {result.container}")
    print(f"   Codec:     {result.video_codec or result.audio_codec}")
    print(f"   Size:      {result.size:,} bytes")
    print(f"   Direct URL: {result.url[:70]}...\n")

    # 2. Extract high quality audio-only stream (Opus / AAC)
    print("2. Extracting high-bitrate audio stream...")
    audio = get_stream_url(url, audio_only=True, quality="high")
    print(f"   Quality:   {audio.quality} (itag {audio.itag})")
    print(f"   Codec:     {audio.audio_codec}")
    print(f"   Size:      {audio.size:,} bytes")
    print(f"   Audio URL: {audio.url[:70]}...\n")

    # 3. List available formats
    print("3. Available formats (top 5):")
    formats = list_formats(url)
    for fmt in formats[:5]:
        res = fmt.get("quality") or fmt.get("resolution") or "audio"
        codec = fmt.get("video_codec") or fmt.get("audio_codec") or "unknown"
        size_mb = f"{fmt.get('size', 0) / 1024 / 1024:.1f} MB" if fmt.get("size") else "N/A"
        print(f"   [itag {fmt.get('itag'):>3}] {res:>6} | {fmt.get('container', ''):>4} | {codec:<15} | {size_mb}")


if __name__ == "__main__":
    main()
