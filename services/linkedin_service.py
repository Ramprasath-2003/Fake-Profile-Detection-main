"""
LinkedIn profile service.

LinkedIn aggressively blocks scraping. Most profile data is only
accessible when logged in. This service attempts to read the public
profile page and returns Private/Restricted if access is denied.
"""

import re
import logging
import requests

from services.base import (
    ProfileData, InvalidURLError, ProfileNotFoundError,
    PrivateProfileError, ScrapingError,
)

logger = logging.getLogger(__name__)

_LINKEDIN_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|company)/([A-Za-z0-9_-]+)/?(?:\?.*)?$"
)


def extract_username(profile_url: str) -> str:
    url = (profile_url or "").strip()
    if not url:
        raise InvalidURLError("Profile URL cannot be empty.")
    if url.startswith("@"):
        username = url.lstrip("@").strip().rstrip("/")
        if username:
            return username
        raise InvalidURLError(f"Invalid LinkedIn handle: {url}")
    match = _LINKEDIN_URL_PATTERN.match(url)
    if match:
        return match.group(1)
    if "/" not in url and re.match(r"^[A-Za-z0-9_-]+$", url):
        return url
    raise InvalidURLError("Invalid LinkedIn URL. Expected: https://www.linkedin.com/in/username")


def fetch_profile(profile_url: str) -> ProfileData:
    username = extract_username(profile_url)

    try:
        resp = requests.get(
            f"https://www.linkedin.com/in/{username}/",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html",
            },
            timeout=10,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        logger.error("LinkedIn request failed for %s: %s", username, exc)
        raise ScrapingError("Failed to connect to LinkedIn. Please try again later.")

    # LinkedIn almost always redirects to login for full data
    if resp.status_code == 404:
        raise ProfileNotFoundError(f"LinkedIn profile '{username}' not found.")

    if resp.status_code == 999 or "authwall" in resp.url.lower():
        # LinkedIn blocks automated access
        return ProfileData(
            platform="linkedin",
            username=username,
            is_private=True,
        )

    page_text = resp.text

    # Check for login redirect
    if "/login" in resp.url or "sign-in" in resp.url.lower():
        return ProfileData(
            platform="linkedin",
            username=username,
            is_private=True,
        )

    # Try to extract from public page / meta tags
    followers = 0
    connections = 0
    bio_length = 0

    desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', page_text, re.I)
    if desc_match:
        bio_length = len(desc_match.group(1))

    fol_match = re.search(r'([\d,]+)\s*followers', page_text, re.I)
    if fol_match:
        followers = int(fol_match.group(1).replace(",", ""))

    conn_match = re.search(r'([\d,]+)\s*connections', page_text, re.I)
    if conn_match:
        connections = int(conn_match.group(1).replace(",", ""))

    has_pic = "profile-photo" in page_text.lower() or "ghost-person" not in page_text.lower()

    if followers == 0 and connections == 0 and bio_length == 0:
        return ProfileData(
            platform="linkedin",
            username=username,
            is_private=True,
        )

    return ProfileData(
        platform="linkedin",
        username=username,
        followers=followers if followers else connections,
        following=connections,
        posts=0,
        bio_length=bio_length,
        has_profile_pic=has_pic,
        has_external_url=False,
        is_private=False,
    )
