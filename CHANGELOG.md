# Changelog

All notable changes to aytube will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2025-09-03

### Fixed
- Rate-limit retry: `_process_formats_html` now raises on empty URLs, triggering retry in `get_stream_url`
- Cache pollution: `list_formats` no longer caches results (was storing bad data with empty adaptive URLs)
- Download 403 errors: `download()` now uses `method="auto"` to fallback to innertube URLs
- Unbound variable: `n_func` initialized before try block in `list_formats`

### Added
- Per-video format cache (5 min TTL) in `get_stream_url` to avoid repeated YouTube requests
- Retry logic with backoff for YouTube rate-limit (429/403/503)
- Innertube API fallback when HTML-built URLs fail

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
