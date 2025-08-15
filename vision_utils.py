
# vision_utils.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image, ImageOps
import cv2

# Lazy-loaded InsightFace app (singleton)
_FACE_APP = None  # type: ignore[attr-defined]


@dataclass
class FaceResult:
    embedding: np.ndarray  # shape (512,), float32, L2-normalized
    crop: Image.Image      # face crop for UI
    quality: float         # detection confidence (det_score)


def ensure_model(device: str = "cpu") -> None:
    """Load InsightFace FaceAnalysis once (RetinaFace + ArcFace/AdaFace)."""
    global _FACE_APP
    if _FACE_APP is not None:
        return
    from insightface.app import FaceAnalysis

    providers = (
        ["CPUExecutionProvider"]
        if device == "cpu"
        else ["CUDAExecutionProvider", "CPUExecutionProvider"]
    )
    app = FaceAnalysis(name="buffalo_l", providers=providers)
    app.prepare(ctx_id=0, det_size=(640, 640))
    _FACE_APP = app


def _pil_to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def detect_and_embed_most_prominent_face(
    img: Image.Image, min_iod_px: int = 80
) -> Optional[FaceResult]:
    """Detect faces, pick the largest, and return its embedding and crop."""
    if _FACE_APP is None:
        ensure_model()

    # Respect EXIF orientation and ensure RGB
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    bgr = _pil_to_bgr(img)
    faces = _FACE_APP.get(bgr)  # type: ignore[attr-defined]
    if not faces:
        return None

    candidates = []
    for f in faces:
        try:
            le, re = f.kps[0], f.kps[1]  # left/right eye landmarks
            iod = float(np.linalg.norm(le - re))
            if iod < float(min_iod_px):
                continue

            x1, y1, x2, y2 = [int(max(0, v)) for v in f.bbox]
            if x2 <= x1 or y2 <= y1:
                continue

            crop_bgr = bgr[y1:y2, x1:x2]
            if crop_bgr.size == 0:
                continue
            crop = Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))

            emb = f.normed_embedding.astype("float32")  # already L2-normalized
            q = float(getattr(f, "det_score", 0.0))
            area = (x2 - x1) * (y2 - y1)
            candidates.append((area, q, emb, crop))
        except Exception:
            continue

    if not candidates:
        return None

    # Select by largest area, break ties by quality
    area, q, emb, crop = sorted(candidates, key=lambda t: (t[0], t[1]), reverse=True)[0]
    return FaceResult(embedding=emb, crop=crop, quality=q)


def cosine_scores(query_emb: np.ndarray, cand_embs: np.ndarray) -> np.ndarray:
    """Return raw cosine similarities (higher is better). Assumes L2-normalized inputs."""
    if cand_embs.size == 0:
        return np.zeros((0,), dtype=np.float32)
    q = np.asarray(query_emb, dtype=np.float32).reshape(-1)
    C = np.asarray(cand_embs, dtype=np.float32)  # shape (N, D)
    return C @ q  # (N,)


def normalize_to_percent(
    scores: np.ndarray, p_low: float = 10.0, p_high: float = 99.0
) -> np.ndarray:
    """Map raw scores to 0–100 via per-run percentiles, with clipping."""
    scores = np.asarray(scores, dtype=np.float32)
    if scores.size == 0:
        return scores.astype(np.int32)

    lo = float(np.percentile(scores, p_low))
    hi = float(np.percentile(scores, p_high))

    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        # fallback to min-max or zeros
        s_min, s_max = float(scores.min()), float(scores.max())
        if s_max <= s_min:
            n = np.zeros_like(scores, dtype=np.float32)
        else:
            n = (scores - s_min) / max(1e-6, (s_max - s_min))
    else:
        n = (scores - lo) / max(1e-6, (hi - lo))

    n = np.clip(n, 0.0, 1.0)
    return np.rint(n * 100.0).astype(np.int32)


def percent_to_hex(percent: int) -> str:
    """HSV hue 0→120 mapped from 0→100 percent, s=0.85, v=0.90 -> #rrggbb."""
    import colorsys

    p = max(0, min(100, int(percent))) / 100.0
    hue_deg = 120.0 * p  # 0 (red) .. 120 (green)
    h = hue_deg / 360.0  # colorsys expects 0..1
    s, v = 0.85, 0.90
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

