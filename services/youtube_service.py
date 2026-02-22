"""
YouTube channel service.

Uses the public YouTube Data API v3 (no key) fallback: scrapes the
public channel page for subscriber count, video count, and description.
Also detects hidden subscriber counts.
"""

import re
import logging
import requests

from services.base import (
    ProfileData, InvalidURLError, ProfileNotFoundError,
    PrivateProfileError, ScrapingError,
)

logger = logging.getLogger(__name__)

_YT_URL_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/@([A-Za-z0-9_.-]+)/?(?:\?.*)?$"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/(?:channel|c|user)/([A-Za-z0-9_.-]+)/?(?:\?.*)?$"),
]


def extract_username(profile_url: str) -> str:
    url = (profile_url or "").strip()
    if not url:
        raise InvalidURLError("Profile URL cannot be empty.")
    if url.startswith("@"):
        username = url.lstrip("@").strip().rstrip("/")
        if username:
            return username
        raise InvalidURLError(f"Invalid YouTube handle: {url}")
    for pattern in _YT_URL_PATTERNS:
        match = pattern.match(url)
        if match:
            return match.group(1)
    if "/" not in url and re.match(r"^[A-Za-z0-9_.-]+$", url):
        return url
    raise InvalidURLError("Invalid YouTube URL. Expected: https://www.youtube.com/@channel")


def fetch_profile(profile_url: str) -> ProfileData:
    username = extract_username(profile_url)

    # Try /@handle first, fallback to /c/
    urls_to_try = [
        f"https://www.youtube.com/@{username}",
        f"https://www.youtube.com/c/{username}",
    ]

    page_text = ""
    found = False

    for url in urls_to_try:
        try:
            resp = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=10,
            )
            if resp.status_code == 200 and "channel" in resp.text.lower()[:5000]:
                page_text = resp.text
                found = True
                break
        except requests.RequestException:
            continue

    if not found:
        raise ProfileNotFoundError(f"YouTube channel '@{username}' not found.")

    # Detect hidden subscriber count
    hidden_subs = '"hiddenSubscriberCount":true' in page_text
    if hidden_subs:
        return ProfileData(
            platform="youtube",
            username=username,
            is_private=True,
            extra={"reason": "Hidden subscriber count"},
        )

    # Extract stats
    subscribers = 0
    videos = 0
    bio_length = 0
    has_pic = True

    # subscriberCountText
    sub_match = re.search(r'"subscriberCountText":\{"simpleText":"([\d.]+[KMB]?) subscriber', page_text)
    if sub_match:
        raw = sub_match.group(1)
        subscribers = _parse_abbrev(raw)

    # videoCountText
    vid_match = re.search(r'"videoCountText".*?"([\d,]+)\s*video', page_text)
    if vid_match:
        videos = int(vid_match.group(1).replace(",", ""))

    # Channel description
    desc_match = re.search(r'"description":"((?:[^"\\]|\\.)*)"', page_text)
    if desc_match:
        bio_length = len(desc_match.group(1))

    # Avatar
    if '"avatar"' not in page_text:
        has_pic = False

    has_url = bool(re.search(r'"channelExternalLinkViewModel"', page_text))

    return ProfileData(
        platform="youtube",
        username=username,
        followers=subscribers,
        following=0,
        posts=videos,
        bio_length=bio_length,
        has_profile_pic=has_pic,
        has_external_url=has_url,
        is_private=False,
    )


def _parse_abbrev(text: str) -> int:
    """Parse abbreviated numbers like '1.2M', '500K', '3B'."""
    text = text.strip().upper().replace(",", "")
    multiplier = 1
    if text.endswith("K"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith("B"):
        multiplier = 1_000_000_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return 0
