# aytube 🚀

[![PyPI version](https://img.shields.io/pypi/v/aytube.svg?color=blue)](https://pypi.org/project/aytube/)
[![PyPI downloads](https://img.shields.io/pypi/dm/aytube.svg)](https://pypi.org/project/aytube/)
[![Python versions](https://img.shields.io/pypi/pyversions/aytube.svg)](https://pypi.org/project/aytube/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Ultra-fast YouTube Video & Audio Downloader and Direct Stream Extractor in Python.**  
A modern, lightweight alternative to **`pytube`** and **`yt-dlp`** that works cleanly without `HTTP 403 Forbidden` errors, without heavy dependencies, and with full cookie support.

---

## ⚡ Why AyTube? (Comparison)

If you've used `pytube` recently, you know it constantly breaks with `HTTP 403 Forbidden` and cipher errors. If you've used `yt-dlp`, it is a 15+ MB package that requires external JavaScript challenge solver scripts and complex setups.

**AyTube is designed to be the fastest, simplest, and most reliable Python YouTube extractor:**

| Feature | `aytube` | `pytube` | `yt-dlp` |
|:---|:---:|:---:|:---:|
| **Working in 2025 / 2026** | ✅ Yes | ❌ Broken (`403 Forbidden`) | ⚠️ Requires JS challenge solvers |
| **Package Size** | **< 60 KB** (Zero bloat) | ~100 KB | ~15+ MB |
| **Python Dependencies** | **0** (Standard library only) | 0 | Multiple |
| **Direct Stream Extraction** | ✅ Instant Google Video URLs | ❌ Often 403 | ✅ Yes |
| **4K (2160p), 1080p, 60fps** | ✅ All resolutions | ❌ Restricted | ✅ Yes |
| **Audio Extraction (Opus / AAC)** | ✅ High-bitrate streams | ⚠️ Hit or miss | ✅ Yes |
| **Cookie Authentication** | ✅ Automatic & manual Netscape | ❌ No | ✅ Yes |
| **Byte Range Stream Verification** | ✅ Built-in Partial Content check | ❌ No | ❌ No |
| **CLI with Resumable Downloads** | ✅ Built-in | ⚠️ Basic | ✅ Yes |

---

## 📦 Installation

Install `aytube` from PyPI:

```bash
pip install aytube
```

Or install the latest version from source:

```bash
git clone https://github.com/Sinchu-xD/AyTube.git
cd AyTube
pip install -e .
```

*Requirements: Python 3.10+ (and optional Node.js for signature cipher fallback).*

---

## 🚀 Quick Start (Python)

### 1. Extract Direct Playable Stream URL

```python
from aytube import get_stream_url

# Extract highest available quality (e.g. 4K / 1080p)
result = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

print(result.url)        # Direct playable Google Video CDN URL
print(result.quality)    # e.g., "2160p" or "1080p"
print(result.size)       # File size in bytes
print(result.title)      # Video title
```

### 2. Specific Video Quality (1080p, 720p, 480p, 360p)

```python
from aytube import get_stream_url

# Pick 1080p stream
res_1080p = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", quality="1080p")
print(res_1080p.url)

# Pick 720p stream
res_720p = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", quality="720p")
print(res_720p.url)
```

### 3. Extract Audio Stream (Opus / AAC)

```python
from aytube import get_stream_url

audio = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", audio_only=True, quality="high")
print(f"Codec: {audio.audio_codec}, Quality: {audio.quality}, URL: {audio.url}")
```

### 4. Download Video or Audio

```python
from aytube import download

# Download 1080p video
path = download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", quality="1080p", output="video.mp4")

# Download audio only
audio_path = download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", audio_only=True, output="audio.m4a")
```

### 5. Using Cookies (Bypass Age Verification & Protected Streams)

AyTube automatically detects `cookies_file` in your working directory, or you can provide the path explicitly:

```python
from aytube import get_stream_url, download

# Provide Netscape-format cookies
result = get_stream_url(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    cookies_file="cookies_file",
    quality="1080p"
)
```

---

## 💻 CLI Commands

AyTube includes a full-featured, zero-dependency command line interface:

```bash
# 1. Get direct stream URL (1080p)
aytube get "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q 1080p

# 2. Get direct stream URL as JSON
aytube get "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -j

# 3. List all available 27 video/audio formats with itag, resolution, and sizes
aytube list "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 4. Download video with progress bar
aytube download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q 1080p -o my_video.mp4

# 5. Download audio only
aytube download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -a -o song.m4a

# 6. Resume interrupted download using HTTP Range requests
aytube resume "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -o my_video.mp4

# 7. Search YouTube directly
aytube search "lofi hip hop" -N 5

# 8. Download HD thumbnail (1280x720)
aytube thumb "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -o thumbnail.jpg

# 9. Get video metadata
aytube info "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 10. List video subtitles / captions
aytube subs "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 11. Batch download from URL list
aytube batch urls.txt -q 720p -n 4
```

### CLI Flags Reference

| Option | Flag | Description |
|:---|:---|:---|
| `--quality` | `-q` | Video resolution: `best`, `2160p`, `1440p`, `1080p`, `720p`, `480p`, `360p`, `audio` |
| `--audio` | `-a` | Audio stream only |
| `--output` | `-o` | Output file path or directory |
| `--cookies` | `-c` | Path to Netscape `cookies_file` |
| `--proxy` | `-p` | HTTP / HTTPS proxy URL |
| `--format` | `-f` | Specific YouTube itag format (e.g. `137`, `251`) |
| `--json` | `-j` | Output result as formatted JSON |
| `--max-results` | `-N` | Maximum search/related results |
| `--concurrent` | `-n` | Number of concurrent downloads for batch mode |

---

## 🎯 Supported Stream Formats (Itags)

| ITAG | Resolution | FPS | Container | Video Codec | Audio Codec | Type |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **401** | 2160p (4K) | 25/60 | MP4 | AV1 | — | Video (DASH) |
| **313** | 2160p (4K) | 25/60 | WebM | VP9 | — | Video (DASH) |
| **400** | 1440p (2K) | 25/60 | MP4 | AV1 | — | Video (DASH) |
| **271** | 1440p (2K) | 25/60 | WebM | VP9 | — | Video (DASH) |
| **137** | 1080p (FHD) | 25/60 | MP4 | H.264 (AVC) | — | Video (DASH) |
| **248** | 1080p (FHD) | 25/60 | WebM | VP9 | — | Video (DASH) |
| **399** | 1080p (FHD) | 25/60 | MP4 | AV1 | — | Video (DASH) |
| **136** | 720p (HD) | 25/60 | MP4 | H.264 (AVC) | — | Video (DASH) |
| **247** | 720p (HD) | 25/60 | WebM | VP9 | — | Video (DASH) |
| **135** | 480p | 25 | MP4 | H.264 (AVC) | — | Video (DASH) |
| **18** | 360p | 25 | MP4 | H.264 (AVC) | AAC | Pre-muxed Video+Audio |
| **251** | High (~160k) | — | WebM | — | Opus (48kHz) | Audio Only |
| **140** | Medium (~128k) | — | MP4 | — | AAC (m4a) | Audio Only |
| **249** | Low (~50k) | — | WebM | — | Opus | Audio Only |

---

## 🛡️ Cookie Protection & Privacy

AyTube respects your privacy. Cookie files are **never** bundled or published. AyTube reads standard Netscape cookie files exported from your browser, allowing access to age-restricted videos and higher rate limits without sharing your credentials.

---

## 📄 License

Released under the [MIT License](LICENSE).
Created and maintained by [ABHISHEK THAKUR](https://github.com/Sinchu-xD).
