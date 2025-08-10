
from __future__ import annotations
import threading
from queue import Queue
from dataclasses import dataclass
from typing import List

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

from scraper_utils import fetch_html, extract_image_urls, find_next_url, download_image
from vision_utils import ensure_model, detect_and_embed_most_prominent_face, cosine_scores
from vision_utils import normalize_to_percent, percent_to_hex

# Hidden caps (keep UI minimal)
PAGE_DEPTH = 2
MAX_IMAGES = 400


@dataclass
class Candidate:
    url: str
    title: str  # optional; can be empty if not parsed
    date_str: str  # optional; can be empty
    crop: Image.Image
    score_raw: float
    score_pct: int
    color_hex: str


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Face Finder")
        self.geometry("900x640")

        self.query_emb = None
        self.stop_flag = False

        # TODO: build minimal UI widgets
        # - Photo drop/choose area
        # - Forum URL entry (hidden initially)
        # - Search button
        # - Progress label + Cancel button
        # - Results frame (scrollable list of rows)

    # === UI callbacks ===
    def on_choose_photo(self) -> None:
        """Open file dialog, load image, detect most prominent face, show preview, reveal URL field."""
        # TODO: implement
        pass

    def on_search(self) -> None:
        """Start background worker to scrape and match faces."""
        # TODO: spawn thread targeting self.worker_run(url)
        pass

    def on_cancel(self) -> None:
        self.stop_flag = True

    # === Worker ===
    def worker_run(self, start_url: str) -> None:
        """Fetch up to PAGE_DEPTH pages, pull image URLs, download images, detect one face per image, score, and stream results."""
        # Pseudocode outline:
        # - pages = []
        # - html, url = fetch_html(start_url)
        # - pages.append((html, url))
        # - if PAGE_DEPTH > 1: try find_next_url on first page and fetch once more
        # - for each page: image_urls.extend(extract_image_urls(html, url))
        # - iterate image_urls[:MAX_IMAGES]:
        #     if self.stop_flag: break
        #     img = download_image(u); if not img: continue
        #     fr = detect_and_embed_most_prominent_face(img); if not fr: continue
        #     stash embedding + crop + meta
        #     update progress label via `self.after(0, ...)`
        # - compute scores = cosine_scores(query_emb, cand_embs)
        # - percents = normalize_to_percent(scores)
        # - colors = [percent_to_hex(p) for p in percents]
        # - sort by raw score desc and render rows in UI
        pass

    # === Rendering ===
    def render_result_row(self, c: Candidate) -> None:
        """Add a single row to the results list: face (left), color bar + % + title/domain/date + Open button."""
        # TODO: implement minimal row with a Frame, Label (image), Canvas/Frame for color bar, labels, and a Button that opens the URL
        pass


if __name__ == "__main__":
    ensure_model()  # triggers first-run model download; consider moving to first face detection
    app = App()
    app.mainloop()

