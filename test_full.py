#!/usr/bin/env python3
"""
Full test suite for aytube.
Tests video and audio quality selection with URL validation.
"""
import sys
import time
from urllib.parse import urlparse, parse_qs

COOKIES_FILE = "/home/ubuntu/Yt/cookies_file"
PROXY = "http://lfkwsdbc:lzuj67dg0duz@84.247.60.125:6095"
VIDEO_URL = "https://www.youtube.com/watch?v=eK0IIyBlYew"


def validate_url(url: str) -> bool:
    """Check URL has googlevideo domain, signature, and expire."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    if "googlevideo.com" not in parsed.netloc:
        print(f"  FAIL: wrong domain {parsed.netloc}")
        return False

    has_sig = any(k in params for k in ("s", "signature", "sig"))
    if not has_sig:
        sig_like = any(len(v[0]) == 40 and all(c in '0123456789abcdef' for c in v[0])
                       for v in params.values())
        if not sig_like:
            print(f"  FAIL: no signature")
            return False

    if "expire" not in params:
        print(f"  FAIL: no expire")
        return False

    print(f"  PASS: {parsed.netloc[:35]} sig=yes expire=yes")
    return True


def main():
    from aytube import get_stream_url

    print("=" * 60)
    print("  aytube Full Test Suite")
    print("=" * 60)
    all_ok = True

    tests = [
        ("Video 1080p", {"quality": "1080p"}, 137, "1080p"),
        ("Video 720p", {"quality": "720p"}, 136, "720p"),
        ("Video 480p", {"quality": "480p"}, 135, "480p"),
        ("Video best", {"quality": "best"}, 137, "1080p"),
        ("Audio high", {"audio_only": True, "quality": "high"}, 251, "high"),
        ("Audio medium", {"audio_only": True, "quality": "medium"}, 250, "medium"),
        ("Audio low", {"audio_only": True, "quality": "low"}, 249, "low"),
    ]

    for i, (label, kwargs, expected_itag, expected_quality) in enumerate(tests):
        print(f"\n--- {label} ---")
        try:
            r = get_stream_url(
                VIDEO_URL,
                cookies_file=COOKIES_FILE,
                proxy=PROXY,
                **kwargs,
            )
            print(f"  {r.quality} | itag={r.itag} | {r.size:,} bytes | {r.container} | {r.video_codec or r.audio_codec}")

            checks = [
                r.quality == expected_quality,
                r.itag == expected_itag,
                bool(r.url),
                validate_url(r.url),
            ]

            if all(checks):
                print("  PASS")
            else:
                print("  FAIL")
                all_ok = False

        except Exception as e:
            print(f"  FAIL: {e}")
            all_ok = False

        if i < len(tests) - 1:
            time.sleep(15)

    print("\n" + "=" * 60)
    if all_ok:
        print("  ALL TESTS PASSED!")
    else:
        print("  SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
