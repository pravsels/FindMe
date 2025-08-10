
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image

# Lazy import InsightFace in ensure_model() to keep import cost low here.
_FACE_APP = None  # singleton holder

@dataclass
class FaceResult:
    embedding: np.ndarray  # shape (512,), float32, L2-normalized
    crop: Image.Image      # face crop for UI
    quality: float         # e.g., detection score or simple sharpness metric


def ensure_model(device: str = "cpu") -> None:
    """Load InsightFace FaceAnalysis once (RetinaFace + ArcFace/AdaFace).
    TODO:
    - Import here: from insightface.app import FaceAnalysis
    - Create FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
      (or allow GPU if available later)
    - Prepare with det_size=(640, 640)
    - Store in global _FACE_APP
    """
    # TODO: implement
    raise NotImplementedError


def detect_and_embed_most_prominent_face(img: Image.Image, min_iod_px: int = 80) -> Optional[FaceResult]:
    """Detect faces, pick the largest/most prominent, align & embed.
    TODO:
    - Convert PIL->BGR numpy for InsightFace
    - Run _FACE_APP.get(bgr) → faces
    - Filter out tiny faces via inter-ocular distance (kps[0], kps[1]) < min_iod_px
    - Choose the largest bbox face
    - Use face.normed_embedding (float32) as the descriptor (already L2-normalized)
    - Create a PIL crop from bbox for UI
    - Return FaceResult(emb, crop, quality=face.det_score)
    - Return None if no acceptable faces
    """
    # TODO: implement
    return None


def cosine_scores(query_emb: np.ndarray, cand_embs: np.ndarray) -> np.ndarray:
    """Return raw cosine similarities (higher is better).
    Assumes inputs are L2-normalized.
    """
    # TODO: implement (np.dot or (cand_embs @ query_emb))
    raise NotImplementedError


def normalize_to_percent(scores: np.ndarray, p_low: float = 10.0, p_high: float = 99.0) -> np.ndarray:
    """Map raw scores to 0–100 using per-run percentiles (robust to site/model shifts).
    n = clip((s - p10) / (p99 - p10), 0, 1); return rounded integer percents.
    """
    # TODO: implement
    raise NotImplementedError


def percent_to_hex(percent: int) -> str:
    """Map 0→red, 50→orange/yellow, 100→green via HSV hue = 120 * (percent/100).
    TODO: simple HSV→RGB conversion and format as '#rrggbb'.
    """
    # TODO: implement
    raise NotImplementedError

