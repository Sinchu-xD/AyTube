#!/usr/bin/env python3
"""Unit tests for AyTube (offline, no network required)."""

import unittest
from aytube import extract_video_id


class TestExtractVideoId(unittest.TestCase):
    """Test YouTube URL parsing and video ID extraction."""

    def test_standard_watch_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_short_youtu_be_url(self):
        self.assertEqual(
            extract_video_id("https://youtu.be/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_shorts_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_embed_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_watch_with_timestamp(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30"),
            "dQw4w9WgXcQ",
        )

    def test_watch_with_extra_query_params(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmRdnEQy4Q5Z"),
            "dQw4w9WgXcQ",
        )

    def test_http_protocol(self):
        self.assertEqual(
            extract_video_id("http://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_plain_id_passthrough(self):
        vid = extract_video_id("dQw4w9WgXcQ")
        self.assertEqual(vid, "dQw4w9WgXcQ")
        self.assertEqual(len(vid), 11)


if __name__ == "__main__":
    unittest.main()
