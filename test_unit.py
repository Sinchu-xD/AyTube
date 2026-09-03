#!/usr/bin/env python3
"""
aytube - Unit Tests

Tests for internal helpers without making network requests.
Run: python3 test_unit.py
"""

import unittest
from aytube import extract_video_id


class TestExtractVideoId(unittest.TestCase):

    def test_watch_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_youtu_be(self):
        self.assertEqual(
            extract_video_id("https://youtu.be/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_short_url(self):
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

    def test_watch_with_params(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmRdnEQy4Q5Z"),
            "dQw4w9WgXcQ",
        )

    def test_http_url(self):
        self.assertEqual(
            extract_video_id("http://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_11_char_id(self):
        # IDs must be exactly 11 characters
        vid = extract_video_id("https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(len(vid), 11)


if __name__ == "__main__":
    unittest.main()
