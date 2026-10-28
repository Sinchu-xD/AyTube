# Changelog

All notable changes to **aytube** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2026-10-28

### Changed & Refactored
- **Modular Package Architecture:** Restructured the monolithic `__init__.py` (1,463 LOC) and 13 scattered micro-modules into **10 cohesive, balanced core modules** (~80–400 LOC each):
  - `aytube/utils.py`: URL parsing, HTTP request building, cookie auto-discovery, and configuration manager.
  - `aytube/stream.py`: `StreamResult` dataclass, itag mappings, resolution ranking, and byte-range reachability check.
  - `aytube/extractor.py`: Unified `get_stream_url()`, `list_formats()`, playlist fetching, and in-memory format caching.
  - `aytube/cipher.py`: Reverse-engineered signature deciphering (legacy ops and Node.js engine) and anti-throttling n-parameter transformation.
  - `aytube/downloader.py`: Resumable chunked downloads (`Range: bytes=`), lossless FFmpeg muxing, and concurrent thread pool batching.
  - `aytube/metadata.py`: Video metadata, closed captions/subtitles, chapters, channel information, and thumbnail downloads.
  - `aytube/innertube.py`: Internal YouTube API client supporting mobile and device profiles (`ANDROID_VR`, `WEB`, `IOS`, `TV`).
  - `aytube/search.py`: Keyword search query parser and JSON scraper.
  - `aytube/__init__.py`: Clean public API exporting 24 top-level functions and classes.
  - `aytube/__main__.py`: Professional CLI supporting 13 subcommands with structured JSON output.
- Removed over 2,900 lines of duplicate and dead code while preserving 100% feature coverage.

### Added
- **Dedicated Test Suites (`tests/`):**
  - `tests/test_unit.py`: Offline unit tests for URL parsing and raw ID passthrough.
  - `tests/test_stream.py`: Live stream extraction tests for 4K (2160p), 1080p, 720p, 480p, and Opus/AAC audio.
  - `tests/test_cli.sh`: 13 end-to-end integration tests verifying every CLI subcommand.
- **Dedicated Examples Directory (`examples/`):**
  - `examples/basic_usage.py`: Quick start stream extraction and format listing.
  - `examples/batch_download.py`: Multi-video extraction and concurrent downloading.
  - `examples/custom_cookies.py`: Cookie loading and proxy setup demonstration.
- **Enhanced Cookie Discovery:** Automatically searches `cookies.txt`, `cookie.txt`, `cookies_file`, and `~/.config/aytube/` across current directory and user home.

### Security
- Strictly excluded raw cookie files and user credentials in `.gitignore` and `MANIFEST.in`.

---

## [2.1.0] - 2025-09-03

### Added
- Per-video format cache (5 min TTL) in `get_stream_url`
- Retry logic with backoff for YouTube rate-limit (429/403/503)
- Innertube API fallback when HTML-built URLs fail with 403

### Fixed
- Rate-limit retry: `_process_formats_html` now raises on empty URLs
- Cache pollution: `list_formats` no longer caches bad results
- Download 403 errors: uses `method="auto"` for CDN fallback
- Unbound variable: `n_func` initialized before try block

---

## [2.0.0] - 2025-01-15

### Added
- Complete custom YouTube stream extractor from scratch (no yt-dlp/pytube)
- AES-128-CTR signature decryption via Node.js crypto worker
- Support for all YouTube URL formats: watch, shorts, embed, youtu.be
- Quality selection: 1080p, 720p, 480p, 360p, best, worst
- Audio-only mode with codec selection (opus, mp4a)
- Cookie support (Netscape format) with auto-discovery
- Proxy support (HTTP/HTTPS)
- Stream verification via contentLength + HTTP Range HEAD
- n-parameter support for modern YouTube signatures
- Adaptive format URL construction from signatureCipher
- CLI tool (`aytube`) with download, list, search, info commands
- Format listing with resolved URLs
- Search functionality
- Batch download support
- Resume support for interrupted downloads

### Technical
- Primary method: HTML scraping (no dependencies)
- Optional: innertube API with PoToken support
- Bot challenge detection and automatic retry
- ContentLength-based size detection
- MP4 container preference with WebM fallback
