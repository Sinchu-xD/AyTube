#!/usr/bin/env python3
"""
Custom cookies and proxy configuration example using aytube.

Demonstrates bypassing YouTube's datacenter bot checks and rate limits
using Netscape HTTP cookie files and forward proxies.
"""

import os
from aytube import get_stream_url


def main():
    # 1. Automatic cookie discovery:
    # aytube automatically searches the following locations in order:
    #   - Current working directory (./cookies.txt, ./cookie.txt, ./cookies_file)
    #   - User home directory (~/.config/aytube/cookies.txt, ~/cookies.txt)
    # If found, no explicit cookies parameter is needed.

    # 2. Explicit cookies file specification:
    cookie_file = "cookies_file" if os.path.isfile("cookies_file") else None

    # 3. Optional HTTP/SOCKS proxy:
    proxy = None  # e.g., "http://user:pass@proxy.example.com:8080"

    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"Fetching stream with cookies: {cookie_file or 'auto-discovery'}")

    try:
        result = get_stream_url(
            url,
            cookies_file=cookie_file,
            proxy=proxy,
            quality="720p",
        )
        print(f"Success! Direct Google Video URL obtained:")
        print(f"  Title: {result.title}")
        print(f"  URL:   {result.url[:80]}...")
    except Exception as exc:
        print(f"Extraction failed: {exc}")


if __name__ == "__main__":
    main()
