from setuptools import setup, find_packages

setup(
    name="aytube",
    version="1.0.0",
    description="Extract direct YouTube stream URLs from any YouTube URL format",
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
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Video",
        "Topic :: Internet :: WWW/HTTP",
    ],
    keywords="youtube stream extractor download video audio",
    project_urls={
        "Bug Reports": "https://github.com/Sinchu-xD/AyTube/issues",
        "Source": "https://github.com/Sinchu-xD/AyTube",
    },
)
