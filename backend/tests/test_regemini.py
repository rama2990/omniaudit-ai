from app import extractor
from app import seed as seedmod
from app.db import session
from app.models import Termin
from app.pipeline import process_termin


def test_regemini_baca_ulang_item_fake(monkeypatch):
    seedmod.seed(fast=True)
    ok = seedmod.new_upload("TRD2", seedmod.DEMO / "04_kontrak_C_retensi_dan_pph.pdf", "dewi")
    bad = seedmod.new_upload("TRD2", seedmod.DEMO / "05_kontrak_E_salah_hitung.pdf", "dewi")
    process_termin(ok)
    process_termin(bad)

    fake = extractor._fake

    def gemini(pages):
        if "INV/AN/2026/015" in " ".join(w["text"] for p in pages for w in p["words"]):
            raise RuntimeError("quota")
        return {**fake(pages), "mode": "gemini"}

    monkeypatch.setattr(extractor, "mode", lambda: "gemini")
    monkeypatch.setattr(extractor, "_gemini", gemini)
    seedmod.regemini()
    with session() as s:
        assert s.get(Termin, ok).extraction["mode"] == "gemini"
        b = s.get(Termin, bad)
        assert b.extraction["mode"] == "fake" and b.status != "GAGAL_PROSES"  # Gemini gagal → hasil lama tetap
