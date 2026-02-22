"""
Base classes and shared types for all platform services.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Shared Exceptions ────────────────────────────────────────────────
class PlatformError(Exception):
    """Base exception for all platform service errors."""
    pass


class InvalidURLError(PlatformError):
    """Raised when the provided URL is invalid for the platform."""
    pass


class ProfileNotFoundError(PlatformError):
    """Raised when the profile does not exist."""
    pass


class PrivateProfileError(PlatformError):
    """Raised when the profile is private / restricted."""
    pass


class ScrapingError(PlatformError):
    """Raised when scraping fails for an unexpected reason."""
    pass


class RateLimitError(PlatformError):
    """Raised when API rate limits are hit."""
    pass


# ── Universal Profile Data ───────────────────────────────────────────
@dataclass
class ProfileData:
    """
    Unified profile data extracted from any platform.
    Every platform service must return this structure.
    """
    platform: str
    username: str
    followers: int = 0          # flw — followers / subscribers
    following: int = 0          # flg — following / friends
    posts: int = 0              # pos — posts / videos / tweets
    bio_length: int = 0         # bl  — biography / description length
    has_profile_pic: bool = True   # pic — 1/0
    has_external_url: bool = False # lin — 1/0
    is_private: bool = False
    extra: dict = field(default_factory=dict)  # platform-specific extras


# ── Supported platforms & metadata ───────────────────────────────────
PLATFORM_META = {
    "instagram": {
        "name": "Instagram",
        "icon": "fa-instagram",
        "color": "#E1306C",
        "placeholder": "https://www.instagram.com/username/",
    },
    "facebook": {
        "name": "Facebook",
        "icon": "fa-facebook",
        "color": "#1877F2",
        "placeholder": "https://www.facebook.com/username",
    },
    "twitter": {
        "name": "Twitter / X",
        "icon": "fa-x-twitter",
        "color": "#000000",
        "placeholder": "https://x.com/username",
    },
    "threads": {
        "name": "Threads",
        "icon": "fa-threads",
        "color": "#000000",
        "placeholder": "https://www.threads.net/@username",
    },
    "telegram": {
        "name": "Telegram",
        "icon": "fa-telegram",
        "color": "#0088CC",
        "placeholder": "https://t.me/username",
    },
    "linkedin": {
        "name": "LinkedIn",
        "icon": "fa-linkedin",
        "color": "#0A66C2",
        "placeholder": "https://www.linkedin.com/in/username",
    },
    "youtube": {
        "name": "YouTube",
        "icon": "fa-youtube",
        "color": "#FF0000",
        "placeholder": "https://www.youtube.com/@channel",
    },
}
