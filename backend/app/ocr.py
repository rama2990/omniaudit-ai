"""OCR lokal: kata + bbox per halaman (FR-4). PDF digital via PyMuPDF, hasil scan via RapidOCR."""
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
import pymupdf

MIN_WORDS_DIGITAL = 5


@lru_cache(maxsize=1)
def _engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def _raster_words(page: pymupdf.Page, n: int) -> list[dict]:
    zoom = 2.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    result, _ = _engine()(img)
    words = []
    for box, text, score in result or []:
        xs = [p[0] / zoom for p in box]
        ys = [p[1] / zoom for p in box]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        # RapidOCR memberi per baris; dipecah per kata dengan lebar proporsional jumlah karakter
        parts = text.split()
        total = sum(len(p) for p in parts) + max(0, len(parts) - 1)
        cx = x0
        for part in parts:
            pw = (x1 - x0) * len(part) / max(total, 1)
            words.append({"text": part, "bbox": [round(cx, 1), round(y0, 1), round(cx + pw, 1), round(y1, 1)],
                          "conf": round(float(score), 3)})
            cx += pw + (x1 - x0) / max(total, 1)
    return words


def ocr_pdf(path: str | Path) -> list[dict]:
    """[{n, width, height, source: digital|scan, words: [{id, text, bbox, conf}]}]"""
    pages = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            words = [{"text": w[4], "bbox": [round(v, 1) for v in w[:4]], "conf": 1.0}
                     for w in page.get_text("words", sort=True)]
            source = "digital"
            if len(words) < MIN_WORDS_DIGITAL:
                try:
                    words, source = _raster_words(page, i), "scan"
                except Exception:  # noqa: BLE001 - halaman tak terbaca -> field di sini confidence 0
                    words, source = [], "unreadable"
            for j, w in enumerate(words):
                w["id"] = f"p{i}_w{j}"
                w["text"] = unicodedata.normalize("NFKC", w["text"])  # OCR scan: "：" -> ":"
            pages.append({"n": i, "width": page.rect.width, "height": page.rect.height,
                          "source": source, "words": words})
    return pages
