from setuptools import setup, find_packages

setup(
    name="aytube",
    version="2.1.3",
    description="Ultra-fast YouTube Video & Audio Downloader / Stream Extractor in Python (pytube & yt-dlp alternative without 403 Forbidden, 4K/1080p, Cookie support & CLI)",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="ABHISHEK THAKUR",
    author_email="abhiyanshicreation@gmail.com",
    url="https://github.com/Sinchu-xD/AyTube",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "aytube._debug*"]),
    python_requires=">=3.10",
    install_requires=[],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov",
            "black",
            "ruff",
        ],
    },
    entry_points={
        "console_scripts": [
            "aytube=aytube.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Video",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Utilities",
    ],
    keywords="youtube, youtube-downloader, youtube video downloader, youtube audio downloader, pytube, pytube alternative, pytube 403 forbidden fix, yt-dlp, yt-dlp alternative, youtube stream extractor, stream extractor, youtube download, download youtube video, youtube 4k download, youtube 1080p, youtube audio, youtube mp3, youtube mp4, youtube cookies, youtube innertube, innertube api, youtube bot bypass, youtube playlist downloader, youtube shorts downloader, video downloader, audio downloader, direct stream url",
    project_urls={
        "Homepage": "https://github.com/Sinchu-xD/AyTube",
        "Documentation": "https://github.com/Sinchu-xD/AyTube#readme",
        "Bug Reports": "https://github.com/Sinchu-xD/AyTube/issues",
        "Source": "https://github.com/Sinchu-xD/AyTube",
    },
)
