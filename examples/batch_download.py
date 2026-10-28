#!/usr/bin/env python3
"""
Batch extraction and downloading example using aytube.
"""

from aytube import batch_download, get_stream_url


def demo_batch_extraction():
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://www.youtube.com/watch?v=C0DPdy98e4c",
    ]

    print(f"Extracting streams for {len(urls)} videos:")
    for url in urls:
        try:
            r = get_stream_url(url, quality="best")
            size_mb = f"{r.size / 1024 / 1024:.1f} MB" if r.size else "streaming"
            print(f"  [OK] {r.title[:45]:<45} | {r.quality:>5} | {size_mb}")
        except Exception as e:
            print(f"  [FAIL] {url}: {e}")


def demo_batch_download():
    """
    Demonstrates downloading multiple videos concurrently.
    """
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ]
    print("\nBatch download configuration:")
    print("  batch_download(urls, quality='360p', output_dir='./downloads', concurrent=2)")
    # results = batch_download(urls, quality="360p", output_dir="./downloads", concurrent=2)


if __name__ == "__main__":
    demo_batch_extraction()
    demo_batch_download()
