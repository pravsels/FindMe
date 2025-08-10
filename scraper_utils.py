
from __future__ import annotations
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import io
import re
import requests
from bs4 import BeautifulSoup
from PIL import Image

# Reasonable defaults; tweak in app.py if needed
DEFAULT_TIMEOUT = 10.0
MAX_BYTES = 12_000_000
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_SIDE = 1600  # quick downscale cap

def fetch_html(url: str, timeout: float = DEFAULT_TIMEOUT) -> Tuple[str, str]:
    """GET the URL and return (html_text, final_url after redirects).
    TODO:
    - Use requests.get with timeouts and a short UA string.
    - Validate status code; raise or return empty string on failure.
    - Return response.text and response.url (after redirects).
    """
    # TODO: implement
    raise NotImplementedError


def extract_image_urls(html: str, base_url: str) -> List[str]:
    """Extract absolute image URLs from HTML.
    Sources to consider (generic order):
    - <img src>, srcset, data-src, data-original, data-lazy-src
    - <picture><source srcset>
    - <meta property="og:image"> and <link rel="image_src">
    - <a href> that look like images (by extension); optionally HEAD-check.
    Steps:
    - Resolve relatives via urljoin(base_url, found_url)
    - Prefer largest candidate from srcset when width descriptors exist
    - De-dupe (by URL string is fine here; byte-level de-dupe handled later)
    - Return a clean list
    """
    # TODO: implement
    return []


def find_next_url(html: str, base_url: str) -> Optional[str]:
    """Find a pagination link to the next/older page.
    Heuristics:
    - <link rel="next" href="...">
    - <a rel="next">...
    - <a> with text matching r"next|older|more" (case-insensitive)
    Return absolute URL or None.
    """
    # TODO: implement
    return None


def download_image(url: str, max_bytes: int = MAX_BYTES, timeout: float = DEFAULT_TIMEOUT) -> Optional[Image.Image]:
    """Download an image safely and return a Pillow Image (RGB) or None.
    Steps:
    - Stream GET; check Content-Type in ALLOWED_MIME and Content-Length <= max_bytes.
    - Read into BytesIO; open with PIL; auto-rotate by EXIF; convert to RGB.
    - Downscale if max side > MAX_SIDE (keep aspect), for speed/memory.
    - Return Image or None on any failure.
    """
    # TODO: implement
    return None

