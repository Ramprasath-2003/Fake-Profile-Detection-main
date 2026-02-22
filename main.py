"""
FastAPI application — Universal Social Media Fake Profile Detection.

Supported platforms: Instagram, Facebook, Twitter/X, Threads, Telegram, LinkedIn, YouTube.

Routes:
  GET  /              → redirect to login or dashboard
  GET  /login         → login page
  POST /login         → authenticate
  GET  /logout        → clear session
  GET  /dashboard     → main page (select platform, enter URL)
  POST /analyze       → form-based analysis (renders result page)
  POST /api/analyze-account → JSON API endpoint
"""

import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from starlette.middleware.sessions import SessionMiddleware

from services.base import (
    ProfileData, PLATFORM_META,
    InvalidURLError, ProfileNotFoundError,
    PrivateProfileError, ScrapingError, RateLimitError,
)
from services import (
    instagram_service,
    facebook_service,
    twitter_service,
    threads_service,
    telegram_service,
    linkedin_service,
    youtube_service,
)
from services.feature_engineering import profile_to_features, compute_engineered_features
from services.prediction_service import load_model_at_startup, predict

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Templates ────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ── Credentials ──────────────────────────────────────────────────────
VALID_USERNAME = "ram"
VALID_PASSWORD = "ram@2003"

# ── Platform service dispatcher ──────────────────────────────────────
PLATFORM_SERVICES = {
    "instagram": instagram_service,
    "facebook": facebook_service,
    "twitter": twitter_service,
    "threads": threads_service,
    "telegram": telegram_service,
    "linkedin": linkedin_service,
    "youtube": youtube_service,
}

VALID_PLATFORMS = set(PLATFORM_SERVICES.keys())

# ── Simple in-memory cache (TTL = 5 min) ─────────────────────────────
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 300  # seconds

def _cache_key(platform: str, url: str) -> str:
    return f"{platform}::{url.strip().lower()}"

def _get_cached(key: str) -> Optional[dict]:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None

def _set_cache(key: str, data: dict):
    _cache[key] = (time.time(), data)

# ── Simple rate limiter (per IP, 30 req / min) ───────────────────────
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 30
RATE_WINDOW = 60  # seconds

def _check_rate_limit(client_ip: str):
    now = time.time()
    timestamps = _rate_store[client_ip]
    # Purge old entries
    _rate_store[client_ip] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(_rate_store[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a minute.")
    _rate_store[client_ip].append(now)


# ── Lifespan: load model at startup ─────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model_at_startup()
    logger.info("ML model and scaler loaded successfully.")
    yield


app = FastAPI(
    title="Fake Profile Detection",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key="fake-profile-detection-secret-key-2026")


# ── Pydantic models ─────────────────────────────────────────────────
class AnalyzeAccountRequest(BaseModel):
    platform: str
    profile_url: str

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v):
        v = v.strip().lower()
        if v not in VALID_PLATFORMS:
            raise ValueError(f"Unsupported platform: {v}. Supported: {', '.join(sorted(VALID_PLATFORMS))}")
        return v


class AnalyzeAccountResponse(BaseModel):
    platform: str
    username: str
    status: str              # "Public" | "Private"
    prediction: str          # "Fake" | "Real" | "Unknown"
    risk_score: Optional[float]
    risk_level: str          # "Low" | "Medium" | "High" | "Restricted"


# ── Helper ───────────────────────────────────────────────────────────
def _is_logged_in(request: Request) -> bool:
    return request.session.get("logged_in", False)


def _run_analysis(platform: str, profile_url: str) -> dict:
    """
    Core analysis pipeline: platform + URL → scrape → features → predict.

    Returns early with Private status if account is restricted.
    """
    if platform not in PLATFORM_SERVICES:
        raise InvalidURLError(f"Unsupported platform: {platform}")

    service = PLATFORM_SERVICES[platform]
    profile: ProfileData = service.fetch_profile(profile_url)

    # ── PRIVATE / RESTRICTED → return early ──
    if profile.is_private:
        return {
            "platform": platform,
            "platform_meta": PLATFORM_META.get(platform, {}),
            "username": profile.username,
            "status": "Private",
            "prediction": "Unknown",
            "risk_score": None,
            "risk_level": "Restricted",
            "profile": None,
            "engineered_features": None,
        }

    # ── PUBLIC → extract features → predict ──
    features = profile_to_features(profile)
    result = predict(features)
    engineered = compute_engineered_features(profile)

    return {
        "platform": platform,
        "platform_meta": PLATFORM_META.get(platform, {}),
        "username": profile.username,
        "status": "Public",
        "prediction": result.prediction,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "profile": {
            "followers": profile.followers,
            "following": profile.following,
            "posts": profile.posts,
            "bio_length": profile.bio_length,
            "has_profile_pic": profile.has_profile_pic,
            "has_external_url": profile.has_external_url,
        },
        "engineered_features": engineered,
    }


# ══════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════

# ── Login / Logout ───────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if _is_logged_in(request):
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _is_logged_in(request):
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == VALID_USERNAME and password == VALID_PASSWORD:
        request.session["logged_in"] = True
        request.session["username"] = username
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Invalid username or password"}
    )


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


# ── Dashboard ────────────────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "platforms": PLATFORM_META,
            "result": None,
            "error": None,
            "selected_platform": "instagram",
            "profile_url": "",
        },
    )


# ── Form POST analysis ──────────────────────────────────────────────
@app.post("/analyze", response_class=HTMLResponse)
async def analyze_form(
    request: Request,
    platform: str = Form(...),
    profile_url: str = Form(...),
):
    if not _is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)

    _check_rate_limit(request.client.host if request.client else "unknown")

    error = None
    result = None

    platform = platform.strip().lower()
    if platform not in VALID_PLATFORMS:
        error = f"Unsupported platform: {platform}"
    else:
        # Check cache
        ck = _cache_key(platform, profile_url)
        cached = _get_cached(ck)
        if cached:
            result = cached
        else:
            try:
                result = _run_analysis(platform, profile_url)
                _set_cache(ck, result)
            except InvalidURLError as exc:
                error = str(exc)
            except ProfileNotFoundError as exc:
                error = str(exc)
            except PrivateProfileError as exc:
                error = str(exc)
            except RateLimitError as exc:
                error = str(exc)
            except ScrapingError as exc:
                error = str(exc)
            except Exception:
                logger.exception("Unexpected error during analysis")
                error = "An unexpected error occurred. Please try again later."

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "platforms": PLATFORM_META,
            "result": result,
            "error": error,
            "selected_platform": platform,
            "profile_url": profile_url,
        },
    )


# ── JSON API endpoint ───────────────────────────────────────────────
@app.post("/api/analyze-account", response_model=AnalyzeAccountResponse)
async def api_analyze_account(body: AnalyzeAccountRequest, request: Request):
    _check_rate_limit(request.client.host if request.client else "unknown")

    ck = _cache_key(body.platform, body.profile_url)
    cached = _get_cached(ck)
    if cached:
        return AnalyzeAccountResponse(
            platform=cached["platform"],
            username=cached["username"],
            status=cached["status"],
            prediction=cached["prediction"],
            risk_score=cached["risk_score"],
            risk_level=cached["risk_level"],
        )

    try:
        result = _run_analysis(body.platform, body.profile_url)
        _set_cache(ck, result)
    except InvalidURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PrivateProfileError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except ScrapingError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return AnalyzeAccountResponse(
        platform=result["platform"],
        username=result["username"],
        status=result["status"],
        prediction=result["prediction"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
    )


# ── Legacy endpoint (backward compat) ────────────────────────────────
@app.post("/api/analyze")
async def api_analyze_legacy(request: Request):
    body = await request.json()
    profile_url = body.get("profile_url", "")
    platform = body.get("platform", "instagram")
    req = AnalyzeAccountRequest(platform=platform, profile_url=profile_url)
    return await api_analyze_account(req, request)
