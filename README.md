# aytube

**Extract direct YouTube stream URLs — without yt-dlp, pytube, or any external tool.**

Fully custom implementation from scratch. Supports video/audio quality selection, cookies, proxies, and automatic rate-limit handling.

**Version:** 2.1.0 | **Python:** 3.10+ | **License:** MIT

## Features

- Any URL format — watch, shorts, embed, youtu.be
- Video quality — 4K, 1080p, 720p, 480p, 360p, best, worst
- Audio only — high/medium/low quality (opus, m4a)
- Cookie support — Netscape-format cookies for age-restricted videos
- Proxy support — HTTP/HTTPS proxies
- Automatic retry on rate-limit (429/403/503)
- Modern cipher — AES-128-CTR signature decryption via Node.js worker
- Zero heavy dependencies — only stdlib + Node.js (for cipher only)
- Stream verification — confirms URLs have real bytes

## Installation

```bash
pip install -e .
```

**Requirements:**
- Python 3.10+
- Node.js (for signature cipher decryption on modern YouTube)

## Quick Start

```python
from aytube import get_stream_url

# Basic usage
result = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(result.url)        # Direct playable stream URL
print(result.quality)    # e.g. "2160p"
print(result.size)       # File size in bytes
print(result.title)      # Video title

# Quality selection
result = get_stream_url(url, quality="1080p")

# Audio only
result = get_stream_url(url, audio_only=True, quality="high")

# With cookies (for age-restricted / rate-limited videos)
result = get_stream_url(url, cookies_file="/path/to/cookies_file")

# With proxy
result = get_stream_url(url, proxy="http://127.0.0.1:8080")
```

## CLI Usage

```bash
# List formats
aytube list "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Download
aytube download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q 1080p

# Get stream URL
aytube get "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q 720p

# Audio only
aytube download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --audio

# Search
aytube search "lofi hip hop" --max-results 5

# With cookies
aytube download "URL" -c cookies_file -q 1080p

# With proxy
aytube download "URL" -p "http://127.0.0.1:8080"

# Batch download
aytube batch urls.txt -q 720p

# Setup wizard
aytube setup
```

### CLI Options

| Option | Description |
|--------|-------------|
| `-q, --quality QUALITY` | Quality: best/1080p/720p/480p/360p/audio |
| `-a, --audio` | Audio only |
| `-o, --output OUTPUT` | Output file path |
| `-c, --cookies COOKIES` | Cookies file (Netscape format) |
| `-p, --proxy PROXY` | HTTP/HTTPS proxy URL |
| `-f, --format FORMAT` | Format itag (137, 251, etc.) |
| `-N, --max-results N` | Max search results |

## API Reference

### `get_stream_url(url, cookies_file=None, proxy=None, quality=None, audio_only=False, verify=True, timeout=30)`

Extract a playable stream URL from a YouTube video.

**Parameters:**
- `url` — Any YouTube URL (watch, shorts, embed, youtu.be)
- `quality` — Target quality: `"1080p"`, `"720p"`, `"480p"`, `"360p"`, `"4k"`, `"best"`, `"worst"`
- `audio_only` — Return audio-only stream (opus/m4a)
- `cookies_file` — Netscape-format cookies for age-restricted videos
- `proxy` — HTTP/HTTPS proxy URL
- `verify` — Verify URL is accessible before returning

**Returns:** `StreamResult` with `.url`, `.quality`, `.container`, `.size`, `.title`, `.itag`

### `list_formats(url, cookies_file=None, proxy=None)`

List all available stream formats with URLs.

### `get_metadata(url, cookies_file=None, proxy=None)`

Get video metadata without extracting stream URL.

### `download(url, quality="best", audio_only=False, output=None, cookies_file=None, proxy=None)`

Download a video to a file.

```python
from aytube import get_stream_url, list_formats, download, get_metadata

# Get stream URL
result = get_stream_url("https://youtube.com/watch?v=VIDEO_ID", quality="1080p")

# List all formats
formats = list_formats("https://youtube.com/watch?v=VIDEO_ID")

# Get metadata
meta = get_metadata("https://youtube.com/watch?v=VIDEO_ID")
print(meta["title"], meta["duration"])

# Download
path = download("https://youtube.com/watch?v=VIDEO_ID", quality="1080p")
```

## Examples

### Video Quality Selection
```python
r = get_stream_url(url, quality="1080p")
print(f"1080p: {r.quality} {r.size:,} bytes")
```

### Audio Only
```python
r = get_stream_url(url, audio_only=True, quality="high")
print(f"{r.quality} audio: {r.container} {r.audio_codec} {r.size:,} bytes")
```

### With Cookies
```python
result = get_stream_url(
    "https://www.youtube.com/watch?v=VIDEO_ID",
    cookies_file="/path/to/cookies_file",
    quality="1080p",
)
```

### Batch Processing
```python
urls = ["https://youtube.com/watch?v=ID1", "https://youtube.com/watch?v=ID2"]
for url in urls:
    try:
        r = get_stream_url(url, quality="720p")
        print(f"{r.title[:40]}: {r.size:,} bytes")
    except Exception as e:
        print(f"Failed: {e}")
```

## How It Works

1. **URL Parsing** — Extracts video ID from any YouTube URL format
2. **Page Fetch** — Downloads watch page HTML with cookie/proxy support. Auto-retries with cookies on HTTP 429/403/503
3. **Player Response** — Parses `ytInitialPlayerResponse` JSON from HTML
4. **Cipher Detection** — Checks for encrypted `signatureCipher` fields
5. **Key Extraction** — Extracts AES cipher key from player JS
6. **Signature Decryption** — AES-128-CTR with zero counter (symmetric encrypt=decrypt)
7. **URL Construction** — Builds adaptive format URLs with correct itag and signature
8. **Quality Selection** — Picks best format matching quality preference (prefers mp4 + known sizes)
9. **Verification** — Uses `contentLength` from YouTube, falls back to HTTP Range HEAD

## Rate Limits

YouTube rate-limits unauthenticated requests. To avoid this:

1. **Provide `cookies_file`** — authenticated sessions get higher rate limits
2. **Auto-retry** — aytube automatically retries rate-limited requests with cookies
3. **Innertube fallback** — HTML URLs that get 403 automatically fall back to innertube

```python
# Recommended:
result = get_stream_url(url, cookies_file="cookies_file")
```

## Supported Itags

| Itag | Quality | Container | Codec | Type |
|------|---------|-----------|-------|------|
| 401 | 2160p | mp4 | av01 | video-only |
| 313 | 2160p | webm | vp9 | video-only |
| 400 | 1440p | mp4 | av01 | video-only |
| 308 | 1440p | webm | vp9 | video-only |
| 299 | 1080p | mp4 | avc | video-only |
| 303 | 1080p | webm | vp9 | video-only |
| 137 | 1080p | mp4 | avc | video-only |
| 248 | 1080p | webm | vp9 | video-only |
| 136 | 720p | mp4 | avc | video-only |
| 247 | 720p | webm | vp9 | video-only |
| 135 | 480p | mp4 | avc | video-only |
| 244 | 480p | webm | vp9 | video-only |
| 18 | 360p | mp4 | avc+mp4a | muxed |
| 134 | 360p | mp4 | avc | video-only |
| 140 | audio | mp4 | mp4a.40.2 | audio-only |
| 251 | audio | webm | opus | audio-only |
| 250 | audio | webm | opus | audio-only |
| 249 | audio | webm | opus | audio-only |

## License

MIT
