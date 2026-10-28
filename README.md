# aytube 🚀

[![PyPI version](https://img.shields.io/pypi/v/aytube.svg?color=blue)](https://pypi.org/project/aytube/)
[![Python versions](https://img.shields.io/pypi/pyversions/aytube.svg)](https://pypi.org/project/aytube/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Code style](https://img.shields.io/badge/code%20style-PEP%208-brightgreen.svg)](https://peps.python.org/pep-0008/)

**Ultra-fast YouTube Video & Audio Downloader and Direct Stream Extractor in Python.**  
A modern, lightweight alternative to **`pytube`** and **`yt-dlp`** that runs cleanly without `HTTP 403 Forbidden` errors, without bloated dependencies, and with full Netscape cookie support.

---

## ⚡ Why AyTube? (Comparison)

| Feature | `aytube` | `pytube` | `yt-dlp` |
|:---|:---:|:---:|:---:|
| **Working in 2025 / 2026** | ✅ Yes | ❌ Broken (`403 Forbidden`) | ⚠️ Requires external challenge solvers |
| **Package Size** | **< 60 KB** (Zero bloat) | ~100 KB | ~15+ MB |
| **Python Dependencies** | **0** (Standard library only) | 0 | Multiple |
| **Direct Stream Extraction** | ✅ Instant Google Video CDN URLs | ❌ Often 403 | ✅ Yes |
| **4K (2160p), 1080p, 60fps** | ✅ All resolutions | ❌ Restricted | ✅ Yes |
| **Audio Extraction (Opus / AAC)** | ✅ High-bitrate streams | ⚠️ Inconsistent | ✅ Yes |
| **Cookie Auto-Discovery** | ✅ Automatic (`cookies.txt`, `cookie.txt`) | ❌ No | ✅ Manual flags |
| **Byte Range Stream Verification** | ✅ Built-in Range check | ❌ No | ❌ No |
| **Resumable Downloads & Muxing** | ✅ Built-in (`ffmpeg` auto-merge) | ⚠️ Basic | ✅ Yes |
| **CLI with 13 Subcommands** | ✅ Fast & Scriptable | ⚠️ Minimal | ✅ Yes |

---

## 📦 Installation

Install `aytube` from PyPI:

```bash
pip install aytube
```

Or install the latest version directly from source:

```bash
git clone https://github.com/Sinchu-xD/AyTube.git
cd AyTube
pip install -e .
```

*Requirements: Python 3.10+ (Standard library only).*

---

## 🚀 Quick Start (Python)

### 1. Extract Direct Stream URL

```python
from aytube import get_stream_url

# Extract highest available quality (e.g. 4K / 1080p)
result = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

print("Playable URL:", result.url)       # Direct Google Video CDN URL
print("Resolution:  ", result.quality)   # e.g., "2160p" or "1080p"
print("File Size:   ", result.size)      # Size in bytes
print("Title:       ", result.title)     # Video title
```

### 2. Video Quality Selection (1080p, 720p, 480p, 360p)

```python
from aytube import get_stream_url

# Specific resolution
res_1080p = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", quality="1080p")
res_720p  = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", quality="720p")
```

### 3. Extract High-Bitrate Audio Stream (Opus / AAC)

```python
from aytube import get_stream_url

audio = get_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", audio_only=True, quality="high")
print(f"Codec: {audio.audio_codec} | Quality: {audio.quality} | URL: {audio.url}")
```

### 4. Download Video or Audio (with Auto FFmpeg Muxing)

When downloading 1080p or 4K streams that have separate video and audio tracks, `aytube` automatically merges them into a single high-definition MP4 if `ffmpeg` is available on your system:

```python
from aytube import download

# Download 1080p video (auto-muxes audio)
download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", quality="1080p", output="video.mp4")

# Download audio only
download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", audio_only=True, output="audio.m4a")
```

### 5. Resumable Range Downloads

Continue interrupted transfers from where they left off:

```python
from aytube import download_with_resume

download_with_resume(stream_url, output="large_video.mp4")
```

### 6. Cookie Support (Bypass Bot Checks & Rate Limits)

`aytube` automatically checks the current working directory, `~/.config/aytube/`, and your home folder for:
- `cookies.txt`
- `cookie.txt`
- `cookies_file`

You can also pass a path explicitly:

```python
result = get_stream_url(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    cookies_file="cookies.txt",
    quality="1080p"
)
```

> **Tip (1-Click Cookie Exporter):** Use our built-in lightweight browser extension in [`extension/`](extension/) to export YouTube cookies directly to `cookies.txt` in one click.

### 7. Metadata, Subtitles, Chapters & Search

```python
from aytube import get_metadata, list_subtitles, get_chapters, search

# Video metadata
meta = get_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(f"{meta['title']} by {meta['channel_name']} ({meta['duration']})")

# Captions & subtitles
subs = list_subtitles("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Video chapters
chapters = get_chapters("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# YouTube Search
results = search("lofi hip hop", max_results=5)
```

---

## 💻 CLI Commands

AyTube includes a full-featured command line interface:

```bash
# 1. Get direct stream URL (1080p)
aytube get "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q 1080p

# 2. Get stream URL as JSON
aytube get "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -j

# 3. List all available formats with itags, resolutions, and sizes
aytube list "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 4. Download video with progress bar
aytube download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q 1080p -o video.mp4

# 5. Download audio track only
aytube download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -a -o song.m4a

# 6. Resume interrupted download using HTTP Range requests
aytube resume "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -o video.mp4

# 7. Search YouTube directly
aytube search "lofi beats" -N 5

# 8. Download HD thumbnail (1280x720)
aytube thumb "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -o thumbnail.jpg

# 9. Get structured video metadata
aytube info "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 10. List video subtitles / captions
aytube subs "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 11. List video chapters
aytube chapters "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 12. Batch download from file
aytube batch urls.txt -q 720p -n 4

# 13. Interactive configuration wizard
aytube setup
```

### CLI Flags Reference

| Option | Flag | Description |
|:---|:---|:---|
| `--quality` | `-q` | Video resolution: `best`, `2160p`, `1440p`, `1080p`, `720p`, `480p`, `360p`, `high`, `low` |
| `--audio` | `-a` | Audio stream only |
| `--output` | `-o` | Output file path or directory |
| `--cookies` | `-c` | Path to Netscape `cookies.txt` file |
| `--proxy` | `-p` | HTTP / HTTPS proxy URL |
| `--format` | `-f` | Specific YouTube itag format (e.g. `137`, `251`) |
| `--json` | `-j` | Output result as formatted JSON |
| `--concurrent` | `-n` | Number of concurrent downloads for batch mode |
| `--max-results` | `-N` | Maximum results for search queries |
| `--quiet` | | Suppress progress output |

---

## 📁 Repository Architecture

```text
aytube/
├── aytube/
│   ├── __init__.py      # Clean public API exports (24 functions & classes)
│   ├── __main__.py      # CLI dispatcher supporting 13 subcommands
│   ├── cipher.py        # Signature deciphering & anti-throttling n-parameter
│   ├── downloader.py    # Resumable downloads, ffmpeg muxing, and batching
│   ├── extractor.py     # Stream extraction orchestrator, format mapping, & cache
│   ├── innertube.py     # YouTube internal API client (Android VR, Web, iOS, TV)
│   ├── metadata.py      # Video metadata, subtitles, chapters, channel info
│   ├── search.py        # YouTube keyword search query scraper
│   ├── stream.py        # StreamResult dataclass, itags, & Range verification
│   └── utils.py         # URL parser, HTTP fetcher, cookies, & configuration
├── examples/
│   ├── basic_usage.py   # Quick start extraction demonstration
│   ├── batch_download.py# Multi-video concurrent downloading
│   └── custom_cookies.py# Cookie loading & proxy configuration
├── tests/
│   ├── test_unit.py     # 8 offline unit tests
│   ├── test_stream.py   # 7 live Google Video CDN stream extraction tests
│   └── test_cli.sh      # 13 CLI integration tests
├── CHANGELOG.md         # Semantic versioning release history
├── MANIFEST.in          # Packaging inclusion/exclusion rules
├── pyproject.toml       # Modern PEP 517 build configuration
└── setup.py             # Standard setuptools configuration
```

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

## 🧪 Running Tests

```bash
# 1. Run offline unit tests
python3 -m unittest discover tests

# 2. Run live stream resolution test suite
python3 tests/test_stream.py

# 3. Run CLI integration tests
bash tests/test_cli.sh
```

---

## 🛡️ Cookie Protection & Privacy

AyTube respects your security. Cookie files and user credentials are **never** bundled or published. AyTube reads standard Netscape cookie files exported from your browser, allowing access to age-restricted videos and higher rate limits without sharing your credentials.

---

## 📄 License

Released under the [MIT License](LICENSE).  
Created and maintained by [ABHISHEK THAKUR](https://github.com/Sinchu-xD) (`abhiyanshicreation@gmail.com`).
