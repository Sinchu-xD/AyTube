"""
Configuration management for aytube.

Supports saving/loading default settings to a config file.
"""
from __future__ import annotations

import json
import os
import sys


CONFIG_DIR = os.path.expanduser("~/.config/aytube")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "cookies_file": "",
    "proxy": "",
    "default_quality": "best",
    "default_audio_only": False,
    "default_output_dir": ".",
    "default_timeout": 30,
    "verify_streams": True,
    "retry_count": 3,
}


def get_config_path() -> str:
    """Get the config file path, creating directory if needed."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    return CONFIG_FILE


def load_config() -> dict:
    """
    Load configuration from file.

    Returns
    -------
    dict
        Configuration dictionary with defaults merged.
    """
    if not os.path.isfile(CONFIG_FILE):
        return dict(DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        # Merge with defaults
        merged = dict(DEFAULT_CONFIG)
        merged.update(config)
        return merged
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> str:
    """
    Save configuration to file.

    Parameters
    ----------
    config : dict
        Configuration dictionary to save.

    Returns
    -------
    str
        Path to the config file.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)

    # Merge with defaults for any missing keys
    merged = dict(DEFAULT_CONFIG)
    merged.update(config)

    with open(CONFIG_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    return CONFIG_FILE


def get_config(key: str, default=None):
    """Get a single config value."""
    config = load_config()
    return config.get(key, default)


def set_config(key: str, value) -> dict:
    """Set a single config value and save."""
    config = load_config()
    config[key] = value
    save_config(config)
    return config


def setup_wizard():
    """
    Interactive setup wizard for aytube configuration.
    """
    print("=" * 50)
    print("  aytube Setup")
    print("=" * 50)
    print()

    config = load_config()

    # Cookies file
    cookies = config.get("cookies_file", "")
    new_cookies = input(f"Cookies file path [{cookies}]: ").strip()
    if new_cookies:
        config["cookies_file"] = new_cookies
    elif not cookies:
        config["cookies_file"] = ""

    # Proxy
    proxy = config.get("proxy", "")
    new_proxy = input(f"Proxy URL [{proxy}]: ").strip()
    if new_proxy:
        config["proxy"] = new_proxy
    elif not proxy:
        config["proxy"] = ""

    # Default quality
    quality = config.get("default_quality", "best")
    new_quality = input(f"Default quality [{quality}]: ").strip()
    if new_quality:
        config["default_quality"] = new_quality

    # Default output directory
    output_dir = config.get("default_output_dir", ".")
    new_output = input(f"Default output directory [{output_dir}]: ").strip()
    if new_output:
        config["default_output_dir"] = new_output

    # Verify streams
    verify = config.get("verify_streams", True)
    new_verify = input(f"Verify streams before download [{'y' if verify else 'n'}]: ").strip().lower()
    if new_verify in ("y", "n"):
        config["verify_streams"] = new_verify == "y"

    # Save
    path = save_config(config)
    print()
    print(f"Configuration saved to: {path}")
    print()

    # Show current config
    print("Current configuration:")
    for key, value in load_config().items():
        print(f"  {key}: {value}")


def show_config():
    """Display current configuration."""
    config = load_config()
    print("=" * 50)
    print("  aytube Configuration")
    print("=" * 50)
    print()
    for key, value in config.items():
        display = value if value else "(not set)"
        print(f"  {key}: {display}")
    print()
    print(f"Config file: {CONFIG_FILE}")
