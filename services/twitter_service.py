"""
Twitter / X profile service.

Uses the public syndication API (no auth required) to fetch basic profile data.
Falls back to page scraping if syndication is unavailable.
"""

import re
import logging
import requests

from services.base import (
    ProfileData, InvalidURLError, ProfileNotFoundError,
    PrivateProfileError, ScrapingError, RateLimitError,
)

logger = logging.getLogger(__name__)

_TWITTER_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)/?(?:\?.*)?$"
)


def extract_username(profile_url: str) -> str:
    url = (profile_url or "").strip()
    if not url:
        raise InvalidURLError("Profile URL cannot be empty.")
    if url.startswith("@"):
        username = url.lstrip("@").strip().rstrip("/")
        if username and re.match(r"^[A-Za-z0-9_]+$", username):
            return username
        raise InvalidURLError(f"Invalid Twitter handle: {url}")
    match = _TWITTER_URL_PATTERN.match(url)
    if match:
        username = match.group(1)
        if username.lower() in ("home", "explore", "search", "settings", "i", "intent"):
            raise InvalidURLError("The URL points to a Twitter page, not a user profile.")
        return username
    if "/" not in url and re.match(r"^[A-Za-z0-9_]+$", url):
        return url
    raise InvalidURLError("Invalid Twitter URL. Expected: https://x.com/username")


def fetch_profile(profile_url: str) -> ProfileData:
    username = extract_username(profile_url)

    # Try syndication API first (no auth needed, returns JSON)
    try:
        resp = requests.get(
            f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.error("Twitter request failed for %s: %s", username, exc)
        raise ScrapingError("Failed to connect to Twitter/X. Please try again later.")

    if resp.status_code == 429:
        raise RateLimitError("Twitter/X rate limit reached. Please try again in a few minutes.")

    if resp.status_code == 404 or "not found" in resp.text.lower()[:500]:
        raise ProfileNotFoundError(f"Twitter/X account '@{username}' not found.")

    page_text = resp.text

    # Check if protected
    if '"protected":true' in page_text or "These Tweets are protected" in page_text:
        return ProfileData(
            platform="twitter",
            username=username,
            is_private=True,
        )

    # Extract stats from embedded data
    followers = 0
    following = 0
    tweets = 0
    bio_length = 0
    has_pic = True

    fol_match = re.search(r'"followers_count":(\d+)', page_text)
    if fol_match:
        followers = int(fol_match.group(1))

    fri_match = re.search(r'"friends_count":(\d+)', page_text)
    if fri_match:
        following = int(fri_match.group(1))

    tw_match = re.search(r'"statuses_count":(\d+)', page_text)
    if tw_match:
        tweets = int(tw_match.group(1))

    desc_match = re.search(r'"description":"([^"]*)"', page_text)
    if desc_match:
        bio_length = len(desc_match.group(1))

    pic_match = re.search(r'"default_profile_image":true', page_text)
    if pic_match:
        has_pic = False

    url_match = re.search(r'"url":"(https?://[^"]+)"', page_text)
    has_url = bool(url_match)

    return ProfileData(
        platform="twitter",
        username=username,
        followers=followers,
        following=following,
        posts=tweets,
        bio_length=bio_length,
        has_profile_pic=has_pic,
        has_external_url=has_url,
        is_private=False,
    )
