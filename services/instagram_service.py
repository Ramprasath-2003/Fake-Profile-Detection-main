"""
Instagram profile scraping service using instaloader.

Extracts raw profile data from a public Instagram profile.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

import instaloader

logger = logging.getLogger(__name__)


class InstagramError(Exception):
    """Base exception for Instagram service errors."""
    pass


class InvalidURLError(InstagramError):
    """Raised when the provided URL is not a valid Instagram profile URL."""
    pass


class ProfileNotFoundError(InstagramError):
    """Raised when the Instagram profile does not exist."""
    pass


class PrivateProfileError(InstagramError):
    """Raised when the Instagram profile is private."""
    pass


class ScrapingError(InstagramError):
    """Raised when scraping fails for an unexpected reason."""
    pass


@dataclass
class InstagramProfile:
    """Raw profile data extracted from Instagram."""
    username: str
    followers: int
    followees: int
    mediacount: int
    biography: str
    has_profile_pic: bool
    has_external_url: bool
    is_private: bool


# Regex to extract username from Instagram URL
_INSTAGRAM_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?(?:\?.*)?$"
)


def extract_username(profile_url: str) -> str:
    """
    Extract the Instagram username from a profile URL.

    Supports formats:
        - https://www.instagram.com/username/
        - https://instagram.com/username
        - instagram.com/username
        - @username  (direct handle)
        - username   (plain text)

    Raises:
        InvalidURLError: If the URL format is invalid.
    """
    url = (profile_url or "").strip()
    if not url:
        raise InvalidURLError("Profile URL cannot be empty.")

    # Direct handle: @username
    if url.startswith("@"):
        username = url.lstrip("@").strip().rstrip("/")
        if username and re.match(r"^[A-Za-z0-9_.]+$", username):
            return username
        raise InvalidURLError(f"Invalid Instagram handle: {url}")

    # Full URL
    match = _INSTAGRAM_URL_PATTERN.match(url)
    if match:
        username = match.group(1)
        # Filter out non-profile paths
        if username.lower() in ("p", "explore", "reel", "stories", "accounts", "direct"):
            raise InvalidURLError(
                "The URL points to an Instagram page, not a user profile."
            )
        return username

    # Plain username (no slashes, no protocol)
    if "/" not in url and "." not in url and re.match(r"^[A-Za-z0-9_.]+$", url):
        return url

    raise InvalidURLError(
        "Invalid Instagram URL. Expected format: https://www.instagram.com/username/"
    )


def fetch_profile(username: str) -> InstagramProfile:
    """
    Fetch profile data from Instagram using instaloader.

    Args:
        username: The Instagram username to look up.

    Returns:
        InstagramProfile with raw scraped data.

    Raises:
        ProfileNotFoundError: If the account doesn't exist.
        PrivateProfileError: If the account is private.
        ScrapingError: On any other instaloader failure.
    """
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        raise ProfileNotFoundError(f"Instagram account '@{username}' not found.")
    except instaloader.exceptions.ConnectionException as exc:
        error_msg = str(exc).lower()
        if "not found" in error_msg or "404" in error_msg:
            raise ProfileNotFoundError(f"Instagram account '@{username}' not found.")
        logger.error("Connection error fetching @%s: %s", username, exc)
        raise ScrapingError("Failed to connect to Instagram. Please try again later.")
    except Exception as exc:
        logger.error("Unexpected error fetching @%s: %s", username, exc)
        raise ScrapingError("An unexpected error occurred while fetching the profile.")

    if profile.is_private:
        raise PrivateProfileError(
            f"Instagram account '@{username}' is private. Cannot analyze private profiles."
        )

    return InstagramProfile(
        username=profile.username,
        followers=profile.followers,
        followees=profile.followees,
        mediacount=profile.mediacount,
        biography=profile.biography or "",
        has_profile_pic=not profile.is_private and bool(profile.profile_pic_url),
        has_external_url=bool(profile.external_url),
        is_private=profile.is_private,
    )
