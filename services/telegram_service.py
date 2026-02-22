"""
Telegram profile / channel service.

Uses the public t.me preview page to extract channel/group info.
Private groups without public usernames cannot be analyzed.
"""

import re
import logging
import requests

from services.base import (
    ProfileData, InvalidURLError, ProfileNotFoundError,
    PrivateProfileError, ScrapingError,
)

logger = logging.getLogger(__name__)

_TELEGRAM_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]+)/?(?:\?.*)?$"
)


def extract_username(profile_url: str) -> str:
    url = (profile_url or "").strip()
    if not url:
        raise InvalidURLError("Profile URL cannot be empty.")
    if url.startswith("@"):
        username = url.lstrip("@").strip().rstrip("/")
        if username and re.match(r"^[A-Za-z0-9_]+$", username):
            return username
        raise InvalidURLError(f"Invalid Telegram handle: {url}")
    match = _TELEGRAM_URL_PATTERN.match(url)
    if match:
        username = match.group(1)
        if username.lower() in ("joinchat", "addstickers", "proxy", "socks"):
            raise InvalidURLError("The URL points to a Telegram invite, not a public channel.")
        return username
    if "/" not in url and re.match(r"^[A-Za-z0-9_]+$", url):
        return url
    raise InvalidURLError("Invalid Telegram URL. Expected: https://t.me/username")


def fetch_profile(profile_url: str) -> ProfileData:
    username = extract_username(profile_url)

    try:
        resp = requests.get(
            f"https://t.me/{username}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.error("Telegram request failed for %s: %s", username, exc)
        raise ScrapingError("Failed to connect to Telegram. Please try again later.")

    if resp.status_code == 404:
        raise ProfileNotFoundError(f"Telegram channel '@{username}' not found.")

    page_text = resp.text

    # Check if this is a private group / requires invite link
    if "tgme_page_icon" not in page_text and "tgme_page_photo" not in page_text:
        if "joinchat" in page_text.lower() or "private" in page_text.lower()[:1000]:
            return ProfileData(
                platform="telegram",
                username=username,
                is_private=True,
            )

    # "If you have Telegram, you can contact" → not found / empty
    if f"If you have <strong>Telegram</strong>" in page_text and "can contact" in page_text:
        # Still a valid public account, just a user (not channel)
        pass

    members = 0
    bio_length = 0
    has_pic = False

    # Members / subscribers
    mem_match = re.search(r'<div class="tgme_page_extra">(.*?)</div>', page_text, re.S)
    if mem_match:
        extra_text = mem_match.group(1).strip()
        num_match = re.search(r'([\d\s]+)', extra_text)
        if num_match:
            members = int(num_match.group(1).replace(" ", "").replace("\xa0", ""))

    # Description
    desc_match = re.search(r'<div class="tgme_page_description[^"]*">(.*?)</div>', page_text, re.S)
    if desc_match:
        # Strip HTML tags
        desc_text = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
        bio_length = len(desc_text)

    # Profile photo
    has_pic = "tgme_page_photo" in page_text and "img" in page_text

    # Title for display
    title_match = re.search(r'<div class="tgme_page_title[^"]*"><span[^>]*>(.*?)</span>', page_text, re.S)
    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else username

    if members == 0 and bio_length == 0 and not has_pic:
        # Likely a private account or personal user
        return ProfileData(
            platform="telegram",
            username=username,
            is_private=True,
        )

    return ProfileData(
        platform="telegram",
        username=username,
        followers=members,
        following=0,
        posts=0,
        bio_length=bio_length,
        has_profile_pic=has_pic,
        has_external_url=False,
        is_private=False,
        extra={"title": title},
    )
