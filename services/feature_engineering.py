"""
Feature engineering service.

Converts raw Instagram profile data into the ML feature vector
matching the exact column order used during model training.
"""

import numpy as np
from services.instagram_service import InstagramProfile


# ── Column order must match scaler / model training ──────────────────
FEATURE_COLUMNS = [
    "pos",   # mediacount / posts
    "flw",   # followers
    "flg",   # followees / following
    "bl",    # biography length
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


def profile_to_features(profile: InstagramProfile) -> np.ndarray:
    """
    Convert an InstagramProfile into a 1-D numpy feature vector.

    Features not available from public scraping are initialised to 0,
    which is safe because the scaler will center them around the training mean.

    Returns:
        numpy array of shape (17,) in the exact column order expected
        by the scaler and model.
    """
    # Raw features from Instagram scraping
    pos = profile.mediacount
    flw = profile.followers
    flg = profile.followees
    bl = len(profile.biography)
    pic = 1 if profile.has_profile_pic else 0
    lin = 1 if profile.has_external_url else 0

    # Features unavailable from scraping — safe default = 0
    cl = 0
    cz = 0
    ni = 0
    erl = 0
    erc = 0
    lt = 0
    hc = 0
    pr = 0
    fo = 0
    cs = 0
    pi = 0

    feature_vector = np.array(
        [pos, flw, flg, bl, pic, lin, cl, cz, ni, erl, erc, lt, hc, pr, fo, cs, pi],
        dtype=np.float64,
    )

    return feature_vector


def compute_engineered_features(profile: InstagramProfile) -> dict:
    """
    Compute engineered features for informational / display purposes.

    These are NOT fed into the model (not used during training),
    but are useful for the response payload.
    """
    flw = profile.followers
    flg = profile.followees
    pic = 1 if profile.has_profile_pic else 0
    lin = 1 if profile.has_external_url else 0

    # Unavailable features defaulted to 0
    erl, erc, lt, hc, pr, cl = 0, 0, 0, 0, 0, 0

    return {
        "follow_ratio": round(flw / (flg + 1), 4),
        "engagement_ratio": round(erl / (erc + 1), 4),
        "activity_score": lt + hc + pr,
        "social_strength": flw * erc,
        "profile_strength": pic + lin + cl,
    }
