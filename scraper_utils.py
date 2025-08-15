
# scraper_utils.py
from __future__ import annotations
from typing import List, Optional, Tuple, Dict
from urllib.parse import urljoin, urlparse
import os
import io
import re
import requests
from PIL import Image, ImageOps

# Reasonable defaults; tweak in app.py if needed
DEFAULT_TIMEOUT = 10.0
MAX_BYTES = 12_000_000
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_SIDE = 1600  # quick downscale cap
REDDIT_LIMIT = 50  # how many posts to scan per query (subreddit listing)

# ---- Reddit client (lazy) ----
_reddit = None

def _get_reddit():
    """Create or return a cached PRAW client using env vars."""
    global _reddit
    if _reddit is not None:
        return _reddit
    import praw  # lazy import
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "face-finder/0.1 by local-app")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Reddit API credentials missing. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET."
        )
    _reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )
    return _reddit


def fetch_html(url: str, timeout: float = DEFAULT_TIMEOUT) -> Tuple[str, str]:
    """
    Reddit API mode: we don't need HTML. Keep signature for compatibility.
    Returns an empty string and the normalized URL.
    """
    return "", url


def _is_reddit(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(h in host for h in ("reddit.com", "redd.it"))


def _unescape_amp(u: str) -> str:
    # Preview/media URLs often contain HTML-escaped ampersands
    return u.replace("&amp;", "&")

def _image_entries_from_submission(subm) -> List[Dict]:
    """Return a list of dicts with image + post metadata for one submission."""
    entries: List[Dict] = []
    post_url = f"https://www.reddit.com{subm.permalink}"
    title = subm.title or ""
    created = float(getattr(subm, "created_utc", 0.0))

    # 1) Galleries
    if getattr(subm, "is_gallery", False) and getattr(subm, "media_metadata", None):
        mm = subm.media_metadata or {}
        for item in mm.values():
            if isinstance(item, dict):
                u = None
                if "s" in item and isinstance(item["s"], dict) and "u" in item["s"]:
                    u = _unescape_amp(item["s"]["u"])
                elif "p" in item and isinstance(item["p"], list) and item["p"]:
                    u = _unescape_amp(item["p"][-1].get("u", ""))
                if u:
                    entries.append({
                        "image_url": u,
                        "post_url": post_url,
                        "title": title,
                        "created_utc": created,
                    })

    # 2) Direct image link (redd.it/imgur etc. or common extensions)
    try:
        u = str(subm.url or "")
        if re.search(r"\.(jpg|jpeg|png|webp)(?:\?.*)?$", u, re.I) or any(
            h in u for h in ("i.redd.it", "i.imgur.com")
        ):
            entries.append({
                "image_url": u,
                "post_url": post_url,
                "title": title,
                "created_utc": created,
            })
    except Exception:
        pass

    # 3) Preview image for non-direct hosts
    try:
        if getattr(subm, "preview", None):
            imgs = subm.preview.get("images")
            if imgs and isinstance(imgs, list):
                src = imgs[0].get("source", {})
                if src.get("url"):
                    u = _unescape_amp(src["url"])
                    entries.append({
                        "image_url": u,
                        "post_url": post_url,
                        "title": title,
                        "created_utc": created,
                    })
    except Exception:
        pass

    # De-duplicate by image_url (preserve order)
    out, seen = [], set()
    for e in entries:
        iu = e.get("image_url")
        if iu and iu not in seen:
            out.append(e)
            seen.add(iu)
    return out


def extract_image_urls(html: str, base_url: str) -> List[Dict]:
    """
    Use the Reddit API to return entries with BOTH the image URL and the post permalink.
    Returns: List[{"image_url","post_url","title","created_utc"}]
    """
    if not _is_reddit(base_url):
        return []

    r = _get_reddit()
    p = urlparse(base_url)
    parts = [x for x in p.path.strip("/").split("/") if x]

    entries: List[Dict] = []
    try:
        if len(parts) >= 2 and parts[0].lower() == "r":
            subname = parts[1]
            # A specific post
            if len(parts) >= 4 and parts[2].lower() == "comments":
                try:
                    subm = r.submission(url=base_url)
                    entries.extend(_image_entries_from_submission(subm))
                except Exception:
                    pass
            else:
                # Subreddit listing
                for subm in r.subreddit(subname).new(limit=REDDIT_LIMIT):
                    entries.extend(_image_entries_from_submission(subm))
    except Exception:
        pass

    # De-duplicate across submissions by image_url
    out, seen = [], set()
    for e in entries:
        iu = e.get("image_url")
        if iu and iu not in seen:
            out.append(e)
            seen.add(iu)
    return out


def find_next_url(html: str, base_url: str) -> Optional[str]:
    """
    Pagination not needed in API mode. The caller should rely on extract_image_urls().
    """
    return None


def download_image(
    url: str, max_bytes: int = MAX_BYTES, timeout: float = DEFAULT_TIMEOUT
) -> Optional[Image.Image]:
    """Download an image safely and return a Pillow Image (RGB) or None."""
    headers = {"User-Agent": "face-finder/0.1"}
    try:
        with requests.get(url, stream=True, timeout=timeout, headers=headers) as resp:
            ct = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            cl = resp.headers.get("Content-Length")

            # Accept if content-type is in ALLOWED_MIME; otherwise fall back to extension check
            if ct and ct not in ALLOWED_MIME:
                if not re.search(r"\.(jpg|jpeg|png|webp)(?:\?.*)?$", url, re.I):
                    return None

            if cl and int(cl) > max_bytes:
                return None

            buf = io.BytesIO()
            size = 0
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    return None
                buf.write(chunk)
            buf.seek(0)

        im = Image.open(buf)
        # EXIF-aware rotation
        try:
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        im = im.convert("RGB")

        # Downscale large images for speed/memory
        w, h = im.size
        mx = max(w, h)
        if mx > MAX_SIDE:
            scale = MAX_SIDE / float(mx)
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        return im
    except Exception:
        return None
