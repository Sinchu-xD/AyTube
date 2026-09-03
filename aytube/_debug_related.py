"""Debug: find related videos structure in YouTube page"""
import sys, os
sys.path.insert(0, '/home/ubuntu/Yt')

# Try WITHOUT proxy first, with cookies only
from aytube.fetcher import fetch_page
import re

try:
    html = fetch_page('dQw4w9WgXcQ', cookies_file='/home/ubuntu/Yt/cookies_file', timeout=30)
    print(f"HTML length: {len(html)}")

    # Search for videoId patterns near sidebar/watch next
    matches = re.findall(r'"videoId":"(dQw4w9WgXcQ|[a-zA-Z0-9_-]{11})"', html[:50000])
    unique = list(dict.fromkeys(matches))[:10]
    print(f"\nFirst 10 videoIds in first 50KB: {unique}")

    # Check for compactVideoRenderer
    count = html.count('compactVideoRenderer')
    print(f"\ncompactVideoRenderer count: {count}")

    # Check for gridVideoRenderer
    count2 = html.count('gridVideoRenderer')
    print(f"gridVideoRenderer count: {count2}")

    # Check for videoRenderer
    count3 = html.count('videoRenderer')
    print(f"videoRenderer count: {count3}")

    # Find ytInitialData
    m = re.search(r'ytInitialData\s*=\s*({.+?});</script>', html, re.DOTALL)
    if not m:
        m = re.search(r'ytInitialData\s*=\s*({.+?});', html, re.DOTALL)
    if m:
        import json
        data = json.loads(m.group(1))
        # Walk structure looking for video renderers
        found = []
        def walk(obj, path=""):
            if isinstance(obj, dict):
                for k in obj:
                    if k in ("compactVideoRenderer", "videoRenderer", "gridVideoRenderer", "playlistVideoRenderer", "videoWithContextRenderer"):
                        found.append((path + "." + k, list(obj.keys())[:5]))
                    walk(obj[k], path + "." + k)
            elif isinstance(obj, list):
                for i, item in enumerate(obj[:3]):
                    walk(item, path + f"[{i}]")
        walk(data)
        print(f"\nFound renderer types at paths:")
        for p, keys in found[:20]:
            print(f"  {p} -> keys: {keys}")
    else:
        print("No ytInitialData found")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
