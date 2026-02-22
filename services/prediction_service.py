"""
Prediction service.

Loads the trained model and scaler once at import time,
then provides a predict function used by the route.
"""

import os
import logging
from dataclasses import dataclass

import numpy as np
import joblib

logger = logging.getLogger(__name__)

# ── Paths (relative to project root) ────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_PATH = os.path.join(_BASE_DIR, "model", "fake_profile_model.pkl")
_SCALER_PATH = os.path.join(_BASE_DIR, "model", "scaler.pkl")

# ── Threshold & risk logic ───────────────────────────────────────────
FAKE_THRESHOLD = 0.28


@dataclass
class PredictionResult:
    """Result of a fake-profile prediction."""
    prediction: str        # "Fake" or "Real"
    risk_score: float      # probability of being fake (0.0 – 1.0)
    risk_level: str        # "Low" | "Medium" | "High"


# ── Global singletons (loaded once) ─────────────────────────────────
_model = None
_scaler = None


def _load_artifacts():
    """Load model and scaler into module-level globals (called once)."""
    global _model, _scaler
    if _model is not None and _scaler is not None:
        return

    if not os.path.isfile(_MODEL_PATH):
        raise FileNotFoundError(f"Model file not found.")
    if not os.path.isfile(_SCALER_PATH):
        raise FileNotFoundError(f"Scaler file not found.")

    logger.info("Loading ML model and scaler...")
    _scaler = joblib.load(_SCALER_PATH)
    _model = joblib.load(_MODEL_PATH)
    logger.info(
        "Model loaded: %s with %d features.",
        type(_model).__name__,
        getattr(_model, "n_features_in_", "?"),
    )


def load_model_at_startup():
    """Public helper called during app startup to pre-load artifacts."""
    _load_artifacts()


def predict(features: np.ndarray) -> PredictionResult:
    """
    Run prediction on a single feature vector.

    Args:
        features: 1-D numpy array of shape (17,) in the column order
                  expected by the scaler.

    Returns:
        PredictionResult with label, probability, and risk level.
    """
    _load_artifacts()

    # Reshape to 2-D for sklearn
    X = features.reshape(1, -1)

    # Scale features
    X_scaled = _scaler.transform(X)

    # Predict probability
    prob = _model.predict_proba(X_scaled)[0][1]  # P(fake)

    # Apply threshold
    prediction = "Fake" if prob > FAKE_THRESHOLD else "Real"

    # Risk level
    if prob < 0.30:
        risk_level = "Low"
    elif prob < 0.70:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return PredictionResult(
        prediction=prediction,
        risk_score=round(float(prob), 4),
        risk_level=risk_level,
    )
