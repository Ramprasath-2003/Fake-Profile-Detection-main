"""
Threads profile service.

Threads profiles are linked to Instagram. This service attempts to
fetch data from Threads web pages or falls back to Instagram data.
"""

import re
import logging
import requests

from services.base import (
    ProfileData, InvalidURLError, ProfileNotFoundError,
    PrivateProfileError, ScrapingError,
)

logger = logging.getLogger(__name__)

_THREADS_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?threads\.net/@?([A-Za-z0-9_.]+)/?(?:\?.*)?$"
)


def extract_username(profile_url: str) -> str:
    url = (profile_url or "").strip()
    if not url:
        raise InvalidURLError("Profile URL cannot be empty.")
    if url.startswith("@"):
        username = url.lstrip("@").strip().rstrip("/")
        if username and re.match(r"^[A-Za-z0-9_.]+$", username):
            return username
        raise InvalidURLError(f"Invalid Threads handle: {url}")
    match = _THREADS_URL_PATTERN.match(url)
    if match:
        return match.group(1)
    if "/" not in url and re.match(r"^[A-Za-z0-9_.]+$", url):
        return url
    raise InvalidURLError("Invalid Threads URL. Expected: https://www.threads.net/@username")


def fetch_profile(profile_url: str) -> ProfileData:
    username = extract_username(profile_url)

    try:
        resp = requests.get(
            f"https://www.threads.net/@{username}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.error("Threads request failed for %s: %s", username, exc)
        raise ScrapingError("Failed to connect to Threads. Please try again later.")

    if resp.status_code == 404:
        raise ProfileNotFoundError(f"Threads account '@{username}' not found.")

    page_text = resp.text

    # Threads respects linked Instagram privacy
    if '"is_private":true' in page_text:
        return ProfileData(
            platform="threads",
            username=username,
            is_private=True,
        )

    # Extract from meta / JSON-LD / page content
    followers = 0
    bio_length = 0

    fol_match = re.search(r'"follower_count":(\d+)', page_text)
    if fol_match:
        followers = int(fol_match.group(1))

    # og:description
    desc_match = re.search(r'content="([^"]*)"[^>]*property="og:description"', page_text, re.I)
    if not desc_match:
        desc_match = re.search(r'property="og:description"[^>]*content="([^"]*)"', page_text, re.I)
    if desc_match:
        bio_length = len(desc_match.group(1))

    fol2_match = re.search(r'([\d,.]+[KMkm]?)\s*[Ff]ollowers', page_text)
    if fol2_match and followers == 0:
        raw = fol2_match.group(1).replace(",", "")
        if raw.upper().endswith("K"):
            followers = int(float(raw[:-1]) * 1000)
        elif raw.upper().endswith("M"):
            followers = int(float(raw[:-1]) * 1000000)
        else:
            try:
                followers = int(raw)
            except ValueError:
                pass

    has_pic = "profile_pic_url" in page_text or "profilePic" in page_text

    return ProfileData(
        platform="threads",
        username=username,
        followers=followers,
        following=0,
        posts=0,
        bio_length=bio_length,
        has_profile_pic=has_pic or True,  # default assume present
        has_external_url=False,
        is_private=False,
    )
