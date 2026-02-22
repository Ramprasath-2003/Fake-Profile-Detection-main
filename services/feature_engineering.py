"""
Feature engineering service.

Converts unified ProfileData from any platform into the ML feature vector
matching the exact column order used during model training (17 features).
"""

import numpy as np
from services.base import ProfileData


# ── Column order must match scaler / model training ──────────────────
FEATURE_COLUMNS = [
    "pos",   # posts / videos / tweets
    "flw",   # followers / subscribers
    "flg",   # following / friends
    "bl",    # biography / description length
    "pic",   # has profile picture (1/0)
    "lin",   # has external URL / link (1/0)
    "cl",    # (unavailable from scraping) → 0
    "cz",    # (unavailable from scraping) → 0
    "ni",    # (unavailable from scraping) → 0
    "erl",   # (unavailable from scraping) → 0
    "erc",   # (unavailable from scraping) → 0
    "lt",    # (unavailable from scraping) → 0
    "hc",    # (unavailable from scraping) → 0
    "pr",    # (unavailable from scraping) → 0
    "fo",    # (unavailable from scraping) → 0
    "cs",    # (unavailable from scraping) → 0
    "pi",    # (unavailable from scraping) → 0
]


def profile_to_features(profile: ProfileData) -> np.ndarray:
    """
    Convert any platform's ProfileData into a 1-D numpy feature vector.

    Works identically for Instagram, Twitter, Facebook, Threads,
    Telegram, LinkedIn, and YouTube — all map to the same 17 columns.

    Returns:
        numpy array of shape (17,) in the exact column order expected
        by the scaler and model.
    """
    pos = profile.posts
    flw = profile.followers
    flg = profile.following
    bl = profile.bio_length
    pic = 1 if profile.has_profile_pic else 0
    lin = 1 if profile.has_external_url else 0

    # Features unavailable from scraping — safe default = 0
    cl = cz = ni = erl = erc = lt = hc = pr = fo = cs = pi = 0

    return np.array(
        [pos, flw, flg, bl, pic, lin, cl, cz, ni, erl, erc, lt, hc, pr, fo, cs, pi],
        dtype=np.float64,
    )


def compute_engineered_features(profile: ProfileData) -> dict:
    """
    Compute engineered features for display purposes.
    Not fed into the model, but useful for the response payload.
    """
    flw = profile.followers
    flg = profile.following
    pic = 1 if profile.has_profile_pic else 0
    lin = 1 if profile.has_external_url else 0
    pos = profile.posts

    return {
        "follow_ratio": round(flw / (flg + 1), 4),
        "profile_strength": pic + lin,
        "activity_score": pos,
        "social_strength": flw,
    }
