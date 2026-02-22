"""
Instagram profile scraping service using instaloader.
Returns unified ProfileData.
"""

import re
import logging
import instaloader

from services.base import (
    ProfileData, InvalidURLError, ProfileNotFoundError,
    PrivateProfileError, ScrapingError,
)

logger = logging.getLogger(__name__)

_INSTAGRAM_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?(?:\?.*)?$"
)


def extract_username(profile_url: str) -> str:
    url = (profile_url or "").strip()
    if not url:
        raise InvalidURLError("Profile URL cannot be empty.")
    if url.startswith("@"):
        username = url.lstrip("@").strip().rstrip("/")
        if username and re.match(r"^[A-Za-z0-9_.]+$", username):
            return username
        raise InvalidURLError(f"Invalid Instagram handle: {url}")
    match = _INSTAGRAM_URL_PATTERN.match(url)
    if match:
        username = match.group(1)
        if username.lower() in ("p", "explore", "reel", "stories", "accounts", "direct"):
            raise InvalidURLError("The URL points to an Instagram page, not a user profile.")
        return username
    if "/" not in url and re.match(r"^[A-Za-z0-9_.]+$", url):
        return url
    raise InvalidURLError("Invalid Instagram URL. Expected: https://www.instagram.com/username/")


def fetch_profile(profile_url: str) -> ProfileData:
    username = extract_username(profile_url)

    loader = instaloader.Instaloader(
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False,
        compress_json=False, quiet=True,
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

    is_private = profile.is_private

    if is_private:
        return ProfileData(
            platform="instagram",
            username=profile.username,
            is_private=True,
        )

    return ProfileData(
        platform="instagram",
        username=profile.username,
        followers=profile.followers,
        following=profile.followees,
        posts=profile.mediacount,
        bio_length=len(profile.biography or ""),
        has_profile_pic=bool(profile.profile_pic_url),
        has_external_url=bool(profile.external_url),
        is_private=False,
    )
