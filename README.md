# aytube

**Extract direct YouTube stream URLs — without yt-dlp, pytube, or any external tool.**

Fully custom implementation from scratch. Supports video/audio quality selection, cookies, proxies, and automatic rate-limit handling.

## Features

- Any URL format — watch, shorts, embed, youtu.be
- Video quality — 4K, 1080p, 720p, 480p, 360p, best, worst
- Audio only — high/medium/low quality (opus, mp4a)
- Cookie support — Netscape-format cookies_file for age-restricted videos
- Proxy support — HTTP/HTTPS proxies
- Stream verification — confirms URLs have real bytes to play
- Modern cipher — AES-128-CTR signature decryption via Node.js worker
- Zero heavy dependencies — only stdlib + Node.js (for cipher only)

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

# With cookies (for age-restricted / rate-limited videos)
result = get_stream_url(url, cookies_file="/path/to/cookies_file")

# With proxy
result = get_stream_url(url, proxy="http://127.0.0.1:8080")

# Quality selection
result = get_stream_url(url, quality="1080p")

# Audio only
result = get_stream_url(url, audio_only=True, quality="high")
```

## CLI Usage

```bash
# Install the package, then:
aytube "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
aytube "https://youtube.com/shorts/abc123" --quality 720p --audio
aytube "https://youtu.be/dQw4w9WgXcQ" --cookies cookies_file
aytube "lofi hip hop" --search --max-results 5
aytube "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --list
aytube "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --info --json
aytube "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --subs
aytube "dQw4w9WgXcQ" --thumb --output thumb.jpg
aytube "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --chapters
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
| `-j, --json` | JSON output |
| `-v, --verbose` | Verbose output |
| `-n, --concurrent N` | Concurrent downloads |
| `-N, --max-results N` | Max search results |

## Supported Commands

| Command | Description |
|---------|-------------|
| `aytube <url>` | Download video (default) |
| `aytube get <url>` | Get stream URL |
| `aytube list <url>` | List all available formats |
| `aytube download <url>` | Download video |
| `aytube info <url>` | Show video metadata |
| `aytube search <query>` | Search YouTube |
| `aytube subs <url>` | List available subtitles |
| `aytube thumb <id>` | Download thumbnail |
| `aytube chapters <url>` | Show video chapters |
| `aytube setup` | Setup wizard (cookies, config) |
| `aytube show` | Show current configuration |

## API Reference

### `get_stream_url(url, cookies_file=None, proxy=None, quality=None, audio_only=False, verify=True, timeout=30)`

Extract a playable stream URL from a YouTube video.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | required | Any YouTube URL (watch, shorts, embed, youtu.be) |
| `cookies_file` | `str \| None` | `None` | Path to Netscape-format cookies_file. Auto-discovered from package dir, CWD, or `~/.config/aytube/` on rate limits |
| `proxy` | `str \| None` | `None` | HTTP/HTTPS proxy URL (e.g. `"http://127.0.0.1:8080"`) |
| `quality` | `str \| None` | `None` | Target quality: `"1080p"`, `"720p"`, `"480p"`, `"360p"`, `"4k"`, `"best"`, `"worst"` |
| `audio_only` | `bool` | `False` | If `True`, return audio-only stream (opus/m4a) |
| `verify` | `bool` | `True` | Verify the stream URL is accessible before returning |
| `timeout` | `int` | `30` | Request timeout in seconds |

**Returns:** `StreamResult`

### `StreamResult`

Dataclass with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `url` | `str` | Direct playable stream URL |
| `quality` | `str` | Quality label (e.g. `"1080p"`, `"medium"`) |
| `container` | `str` | Container format (`"mp4"`, `"webm"`) |
| `video_codec` | `str` | Video codec (e.g. `"avc1.640028"`, `"av01.0.12M.08"`) |
| `audio_codec` | `str` | Audio codec (e.g. `"mp4a.40.2"`, `"opus"`) |
| `size` | `int` | File size in bytes |
| `title` | `str` | Video title |
| `video_id` | `str` | YouTube video ID |
| `itag` | `int` | YouTube itag number |
| `mime_type` | `str` | Full MIME type string |
| `raw` | `dict` | Original format dict from YouTube |

### `extract_video_id(url)`

Extract the YouTube video ID from any YouTube URL format.

```python
from aytube import extract_video_id

extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")   # "dQw4w9WgXcQ"
extract_video_id("https://youtu.be/dQw4w9WgXcQ")                  # "dQw4w9WgXcQ"
extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ")    # "dQw4w9WgXcQ"
extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ")     # "dQw4w9WgXcQ"
```

### `list_formats(url, cookies_file=None, proxy=None)`

List all available stream formats for a video.

```python
from aytube import list_formats

formats = list_formats("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
for f in formats:
    print(f"itag={f['itag']} {f['quality']} {f['container']} {f['video_codec'] or f['audio_codec']}")
```

### `get_metadata(url, cookies_file=None, proxy=None)`

Get video metadata without extracting stream URL.

```python
from aytube import get_metadata

meta = get_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(meta["title"])
print(meta["duration"])
print(meta["view_count"])
```

### `download(url, quality="best", audio_only=False, output=None, cookies_file=None, proxy=None, timeout=30)`

Download a video to a file.

```python
from aytube import download

path = download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", quality="1080p")
print(f"Saved to {path}")
```

## Examples

### Video Quality Selection

```python
from aytube import get_stream_url

url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Specific quality
r = get_stream_url(url, quality="1080p")
print(f"1080p: {r.url[:80]}...  size={r.size:,}")

# Best available
r = get_stream_url(url)
print(f"best: {r.quality}  size={r.size:,}")
```

### Audio Only

```python
from aytube import get_stream_url

r = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", audio_only=True)
print(f"{r.quality} audio: {r.container} {r.audio_codec}  {r.size:,} bytes")
```

### With Cookies

```python
from aytube import get_stream_url

# Place cookies_file next to your script, or in the package directory
result = get_stream_url(
    "https://www.youtube.com/watch?v=VIDEO_ID",
    cookies_file="/path/to/cookies_file",
    quality="1080p",
)
```

**Getting cookies_file:**
1. Install the [Get cookies.txt](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) Chrome extension
2. Log into YouTube
3. Click the extension → export cookies in **Netscape format**

**Auto-discovery:** If you don't pass `cookies_file`, aytube will automatically look for `cookies_file` in:
- The package installation directory
- Your current working directory
- `~/.config/aytube/cookies_file`

### With Proxy

```python
from aytube import get_stream_url

result = get_stream_url(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    proxy="http://127.0.0.1:8080",
    quality="720p",
)
```

### Different URL Formats

```python
from aytube import get_stream_url

urls = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    "https://www.youtube.com/embed/dQw4w9WgXcQ",
]

for url in urls:
    r = get_stream_url(url, verify=True)
    print(f"{r.quality} {r.size:,} bytes  {r.title[:40]}")
```

### Batch Processing

```python
from aytube import get_stream_url

urls = [
    "https://www.youtube.com/watch?v=VIDEO_ID_1",
    "https://www.youtube.com/watch?v=VIDEO_ID_2",
]

for url in urls:
    try:
        r = get_stream_url(url, quality="720p")
        print(f"{r.title[:40]}: {r.size:,} bytes")
    except Exception as e:
        print(f"Failed: {e}")
```

## How It Works

1. **URL Parsing** — Extracts video ID from any YouTube URL format
2. **Page Fetch** — Downloads the watch page HTML with cookie/proxy support. Auto-retries with cookies on HTTP 429/403/503
3. **Player Response** — Parses `ytInitialPlayerResponse` JSON from the HTML
4. **Cipher Detection** — Checks if formats have encrypted `signatureCipher` fields
5. **Key Extraction** — Tries multiple strategies to extract the AES cipher key
6. **Signature Decryption** — AES-128-CTR with zero counter (symmetric encrypt=decrypt)
7. **URL Construction** — Builds adaptive format URLs with correct itag and signature parameters
8. **Quality Selection** — Picks the best format matching your quality preference, preferring mp4 container and known sizes
9. **Verification** — Uses `contentLength` from YouTube (most reliable), falls back to HTTP Range HEAD

## Rate Limits

YouTube rate-limits unauthenticated requests. To avoid this:

1. **Provide a `cookies_file`** — authenticated sessions get higher rate limits
2. **Auto-retry** — aytube automatically retries rate-limited requests with cookies if a `cookies_file` is found
3. **Backoff** — exponential backoff between retries (1s → 2s → 4s)

```python
# Recommended for public/production use:
result = get_stream_url(url, cookies_file="cookies_file")
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `HTTP 429: Too Many Requests` | Rate limited | Provide `cookies_file` with authenticated session |
| `AGE_CHECK_REQUIRED` | Age-restricted video | Provide `cookies_file` with authenticated adult session |
| `LIVE_STREAM_OFFLINE` | Stream not live | Try again when the stream is live |
| `UNPLAYABLE` | Region/format restriction | Use a proxy from the target region |
| `Could not decipher signature` | YouTube changed obfuscation | Update player JS parsing; provide cookies |

## Supported Itags

| Itag | Quality | Container | Codec | Type |
|------|---------|-----------|-------|------|
| 401 | 2160p | mp4 | av01 | video-only |
| 313 | 2160p | webm | vp9 | video-only |
| 137 | 1080p | mp4 | avc | video-only |
| 248 | 1080p | webm | vp9 | video-only |
| 136 | 720p | mp4 | avc | video-only |
| 247 | 720p | webm | vp9 | video-only |
| 135 | 480p | mp4 | avc | video-only |
| 18 | 360p | mp4 | avc+mp4a | muxed |
| 134 | 360p | mp4 | avc | video-only |
| 140 | audio | mp4 | mp4a.40.2 | audio-only |
| 251 | audio | webm | opus | audio-only |
| 250 | audio | webm | opus | audio-only |
| 249 | audio | webm | opus | audio-only |

## License

MIT
