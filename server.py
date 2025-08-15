
# server.py
from __future__ import annotations
import io, json, uuid, base64, threading, queue
from typing import Dict, Any, List, Optional
from datetime import datetime
from urllib.parse import urlparse

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from PIL import Image
import numpy as np

from scraper_utils import extract_image_urls, download_image
from vision_utils import (
    ensure_model,
    detect_and_embed_most_prominent_face,
    cosine_scores,
)

# ---------- app ----------
app = FastAPI(title="Find Me!")

# (Optional) allow local dev from any origin; tighten when hosting
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# load model once on startup
ensure_model()

# serve the static index.html without extra deps
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ---------- job manager ----------
class Job:
    __slots__ = ("id", "q", "stop", "thread")

    def __init__(self) -> None:
        self.id = uuid.uuid4().hex
        self.q: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()
        self.stop = False
        self.thread: Optional[threading.Thread] = None

JOBS: Dict[str, Job] = {}

# ---------- helpers ----------
def _img_to_data_url(img: Image.Image, max_side: int = 160, quality: int = 85) -> str:
    im = img.copy()
    w, h = im.size
    m = max(w, h)
    if m > max_side:
        scale = max_side / float(m)
        im = im.resize((int(w * scale), int(h * scale)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"

def _abs_percent(score_raw: float) -> int:
    """Absolute mapping from cosine (-1..1) → 0..100."""
    return int(round(((score_raw + 1.0) / 2.0) * 100.0))

# ---------- worker ----------
def _run_job(job: Job, user_photo_bytes: bytes, forum_url: str, min_score: float) -> None:
    try:
        # 1) Decode user photo & get query embedding
        try:
            img = Image.open(io.BytesIO(user_photo_bytes)).convert("RGB")
        except Exception as e:
            job.q.put({"type": "status", "text": f"Could not open image: {e}"})
            job.q.put({"type": "finalize", "count": 0})
            job.q.put(None)
            return

        fr = detect_and_embed_most_prominent_face(img)
        if not fr:
            job.q.put({"type": "status", "text": "🚫 No clear face detected. Try a sharper, frontal photo."})
            job.q.put({"type": "finalize", "count": 0})
            job.q.put(None)
            return

        job.q.put({"type": "face", "thumb": _img_to_data_url(fr.crop)})
        query_emb = fr.embedding

        # 2) Fetch Reddit images
        job.q.put({"type": "status", "text": f"Fetching Reddit posts… (threshold ≥ {_abs_percent(min_score)}% similarity)"})
        try:
            entries = extract_image_urls("", forum_url)
        except Exception as e:
            job.q.put({"type": "status", "text": f"Failed to fetch posts: {e}"})
            job.q.put({"type": "finalize", "count": 0})
            job.q.put(None)
            return

        if not entries:
            job.q.put({"type": "status", "text": "No images found at that link."})
            job.q.put({"type": "finalize", "count": 0})
            job.q.put(None)
            return

        # Normalize entries (list[str] → list[dict])
        if isinstance(entries[0], str):
            norm = [{"image_url": u, "post_url": u, "title": "", "created_utc": None} for u in entries]
        else:
            norm = entries  # type: ignore[assignment]

        job.q.put({"type": "status", "text": f"Found {len(norm)} image URLs. Downloading…"})

        kept = 0
        for i, entry in enumerate(norm, start=1):
            if job.stop:
                job.q.put({"type": "status", "text": "Canceled."})
                break

            job.q.put({"type": "status", "text": f"Processing image {i}/{len(norm)}"})

            img_url = entry.get("image_url")
            post_url = entry.get("post_url") or img_url
            title = entry.get("title", "") or ""
            ts = entry.get("created_utc", None)
            date_str = ""
            if ts:
                try:
                    date_str = datetime.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d")
                except Exception:
                    date_str = ""

            im = download_image(img_url)
            if im is None:
                continue

            fr_cand = detect_and_embed_most_prominent_face(im)
            if not fr_cand:
                continue

            score = float(cosine_scores(query_emb, np.asarray([fr_cand.embedding], dtype=np.float32))[0])

            if score < min_score:
                continue

            kept += 1
            job.q.put({
                "type": "candidate",
                "post_url": post_url,
                "title": title,
                "date": date_str,
                "score_raw": score,                       # absolute raw cosine
                "score_pct": _abs_percent(score),         # absolute % (no recalibration)
                "thumb": _img_to_data_url(fr_cand.crop),
            })

        # 3) Finalize (absolute mode; no calibration payload)
        job.q.put({"type": "finalize", "count": kept})

    finally:
        job.q.put(None)

# ---------- endpoints ----------
@app.post("/api/analyze")
def start_analyze(
    photo: UploadFile = File(...),
    forum_url: str = Form(...),
    threshold: Optional[str] = Form(None),   # 👈 new
) -> Dict[str, str]:
    # basic validation
    if not forum_url or ("reddit.com" not in forum_url and "redd.it" not in forum_url):
        raise HTTPException(status_code=400, detail="Please paste a public reddit.com link (subreddit or post).")

    # parse threshold
    min_score = 0.0
    if threshold is not None and threshold.strip() != "":
        try:
            min_score = float(threshold)
        except Exception:
            pass
    # clamp to cosine range
    min_score = max(-1.0, min(1.0, min_score))

    data = photo.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty photo upload.")

    job = Job()
    JOBS[job.id] = job

    t = threading.Thread(target=_run_job, args=(job, data, forum_url, min_score), daemon=True)  # 👈 pass min_score
    job.thread = t
    t.start()

    return {"job_id": job.id}

@app.get("/api/stream/{job_id}")
def stream(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    def event_iter():
        # Server-Sent Events: send JSON as data lines
        while True:
            item = job.q.get()
            if item is None:
                break
            # format as SSE
            payload = json.dumps(item, ensure_ascii=False)
            yield f"data: {payload}\n\n"

        # cleanup
        JOBS.pop(job_id, None)

    return StreamingResponse(event_iter(), media_type="text/event-stream")


@app.post("/api/cancel/{job_id}")
def cancel(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        return JSONResponse({"ok": True})
    job.stop = True
    # also push a status so UI gets immediate feedback
    try:
        job.q.put_nowait({"type": "status", "text": "Cancel requested…"})
    except Exception:
        pass
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}
