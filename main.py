"""
FastAPI application — Fake Instagram Profile Detection.

Routes:
  GET  /            → login page
  POST /login       → authenticate
  GET  /logout      → clear session
  GET  /dashboard   → main page (enter Instagram URL)
  POST /analyze     → form-based analysis (renders result page)
  POST /api/analyze → JSON API endpoint
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from starlette.middleware.sessions import SessionMiddleware

from services.instagram_service import (
    extract_username,
    fetch_profile,
    InvalidURLError,
    ProfileNotFoundError,
    PrivateProfileError,
    ScrapingError,
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


# ── Lifespan: load model at startup ─────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model_at_startup()
    logger.info("ML model and scaler loaded successfully.")
    yield


app = FastAPI(
    title="Fake Profile Detection",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key="fake-profile-detection-secret-key-2026")


# ── Pydantic models ─────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    profile_url: str


class AnalyzeResponse(BaseModel):
    username: str
    prediction: str
    risk_score: float
    risk_level: str


# ── Helper ───────────────────────────────────────────────────────────
def _is_logged_in(request: Request) -> bool:
    return request.session.get("logged_in", False)


def _run_analysis(profile_url: str) -> dict:
    """
    Core analysis pipeline: URL → username → scrape → features → predict.
    Returns a dict suitable for both JSON and template responses.
    """
    username = extract_username(profile_url)
    profile = fetch_profile(username)
    features = profile_to_features(profile)
    result = predict(features)
    engineered = compute_engineered_features(profile)

    return {
        "username": profile.username,
        "prediction": result.prediction,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "profile": {
            "followers": profile.followers,
            "following": profile.followees,
            "posts": profile.mediacount,
            "bio_length": len(profile.biography),
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


# ── Dashboard (form page) ───────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(
        "index.html", {"request": request, "result": None, "error": None, "profile_url": ""}
    )


# ── Form POST analysis ──────────────────────────────────────────────
@app.post("/analyze", response_class=HTMLResponse)
async def analyze_form(request: Request, profile_url: str = Form(...)):
    if not _is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)

    error = None
    result = None
    try:
        result = _run_analysis(profile_url)
    except InvalidURLError as exc:
        error = str(exc)
    except ProfileNotFoundError as exc:
        error = str(exc)
    except PrivateProfileError as exc:
        error = str(exc)
    except ScrapingError as exc:
        error = str(exc)
    except Exception:
        logger.exception("Unexpected error during analysis")
        error = "An unexpected error occurred. Please try again later."

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": result, "error": error, "profile_url": profile_url},
    )


# ── JSON API endpoint ───────────────────────────────────────────────
@app.post("/api/analyze", response_model=AnalyzeResponse)
async def api_analyze(body: AnalyzeRequest):
    try:
        result = _run_analysis(body.profile_url)
    except InvalidURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PrivateProfileError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ScrapingError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return AnalyzeResponse(
        username=result["username"],
        prediction=result["prediction"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
    )
