"""
Facebook profile service.

Facebook does not expose a public scraping API. This service extracts
the username and attempts basic public page data via requests.
Most personal profiles are restricted — returns Private early.
"""

import re
import logging
import requests

from services.base import (
    ProfileData, InvalidURLError, ProfileNotFoundError,
    PrivateProfileError, ScrapingError,
)

logger = logging.getLogger(__name__)

_FB_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?facebook\.com/(?:profile\.php\?id=(\d+)|([A-Za-z0-9_.]+))/?(?:\?.*)?$"
)


def extract_username(profile_url: str) -> str:
    url = (profile_url or "").strip()
    if not url:
        raise InvalidURLError("Profile URL cannot be empty.")
    if url.startswith("@"):
        username = url.lstrip("@").strip().rstrip("/")
        if username:
            return username
        raise InvalidURLError(f"Invalid Facebook handle: {url}")
    match = _FB_URL_PATTERN.match(url)
    if match:
        return match.group(1) or match.group(2)
    if "/" not in url and re.match(r"^[A-Za-z0-9_.]+$", url):
        return url
    raise InvalidURLError("Invalid Facebook URL. Expected: https://www.facebook.com/username")


def fetch_profile(profile_url: str) -> ProfileData:
    username = extract_username(profile_url)

    try:
        resp = requests.get(
            f"https://www.facebook.com/{username}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        logger.error("Facebook request failed for %s: %s", username, exc)
        raise ScrapingError("Failed to connect to Facebook. Please try again later.")

    if resp.status_code == 404:
        raise ProfileNotFoundError(f"Facebook account '{username}' not found.")

    page_text = resp.text

    # Facebook almost always restricts personal profile data without login
    if "login" in resp.url.lower() or "checkpoint" in resp.url.lower():
        return ProfileData(
            platform="facebook",
            username=username,
            is_private=True,
        )

    # Try to extract basic public page data from meta tags
    followers = 0
    bio_length = 0

    # og:description often contains page info
    desc_match = re.search(r'<meta\s+(?:name|property)="(?:og:)?description"\s+content="([^"]*)"', page_text, re.I)
    description = desc_match.group(1) if desc_match else ""
    bio_length = len(description)

    # Follower count from page content
    fol_match = re.search(r'([\d,]+)\s*(?:followers|people follow)', page_text, re.I)
    if fol_match:
        followers = int(fol_match.group(1).replace(",", ""))

    likes_match = re.search(r'([\d,]+)\s*(?:people like|likes)', page_text, re.I)
    likes = int(likes_match.group(1).replace(",", "")) if likes_match else 0

    has_pic = 'profile_pic' in page_text.lower() or 'profilePic' in page_text

    # If we got zero signal, treat as restricted
    if followers == 0 and likes == 0 and bio_length == 0:
        return ProfileData(
            platform="facebook",
            username=username,
            is_private=True,
        )

    return ProfileData(
        platform="facebook",
        username=username,
        followers=followers if followers else likes,
        following=0,
        posts=0,
        bio_length=bio_length,
        has_profile_pic=has_pic,
        has_external_url=False,
        is_private=False,
    )
