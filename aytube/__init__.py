"""
aytube - Python YouTube stream extractor and downloader.

Zero third-party dependencies, standard-library based, high-performance streaming.
"""

from __future__ import annotations

__version__ = "2.2.0"
__author__ = "ABHISHEK THAKUR"
__email__ = "abhiyanshicreation@gmail.com"
__license__ = "MIT"

from .downloader import (
    batch_download,
    download,
    download_with_resume,
    get_file_size,
)
from .extractor import (
    get_stream_url,
    list_formats,
    list_playlist,
)
from .metadata import (
    bypass_age_check,
    download_thumbnail,
    get_channel_avatar,
    get_channel_info,
    get_chapters,
    get_metadata,
    get_related_videos,
    get_thumbnails,
    list_subtitles,
)
from .search import search
from .stream import StreamResult, verify_stream
from .utils import (
    extract_video_id,
    find_cookies_path,
    get_config,
    load_config,
    save_config,
    set_config,
    setup_wizard,
    show_config,
)

__all__ = [
    # Core Extraction
    "get_stream_url",
    "list_formats",
    "list_playlist",
    "StreamResult",
    "extract_video_id",
    "verify_stream",
    # Downloads & Muxing
    "download",
    "download_with_resume",
    "batch_download",
    "get_file_size",
    # Metadata & Media
    "get_metadata",
    "list_subtitles",
    "get_thumbnails",
    "download_thumbnail",
    "get_chapters",
    "get_related_videos",
    "get_channel_info",
    "get_channel_avatar",
    "bypass_age_check",
    # Discovery
    "search",
    # Settings & Cookies
    "find_cookies_path",
    "load_config",
    "save_config",
    "get_config",
    "set_config",
    "setup_wizard",
    "show_config",
]
