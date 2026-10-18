"""Uji Gemini sungguhan pada PDF demo: bandingkan hasilnya dengan extractor pola teks (kebenaran dasar PDF seed).

Pakai: isi GEMINI_API_KEY di backend/.env, lalu dari folder backend:
    uv run python scripts/gemini_check.py            (model default)
    GEMINI_MODEL=gemini-pro-latest uv run python scripts/gemini_check.py
"""
import os
import sys
import time

from app import extractor
from app.db import ROOT
from app.ocr import ocr_pdf

if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI")):
    sys.exit("GEMINI_API_KEY belum diisi di backend/.env")

total = ok = 0
for pdf in sorted((ROOT.parent / "demo").glob("*.pdf")):
    pages = ocr_pdf(pdf)
    truth = extractor.ground(extractor._fake(pages), pages)
    t0 = time.time()
    got = extractor.ground(extractor._gemini(pages), pages)
    dt = time.time() - t0
    bad = []
    for n in extractor.WAJIB + extractor.OPSIONAL:
        total += 1
        a, b = extractor.value(truth, n), extractor.value(got, n)
        if a == b:
            ok += 1
        else:
            bad.append(f"{n}: harap {a!r}, dapat {b!r}")
    print(f"{pdf.name}: {dt:.1f} dtk, keyakinan {extractor.confidence(got)}, " + ("semua cocok" if not bad else f"{len(bad)} beda"))
    for line in bad:
        print("   ", line)
print(f"\nCocok {ok}/{total} field ({ok / total:.0%}) dengan model {os.getenv('GEMINI_MODEL', 'gemini-flash-latest')}")
