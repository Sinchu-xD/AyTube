from setuptools import setup, find_packages

setup(
    name="aytube",
    version="1.0.0",
    description="Extract direct YouTube stream URLs without yt-dlp",
    author="User",
    packages=find_packages(),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "aytube=aytube.__main__:main",
        ],
    },
)
