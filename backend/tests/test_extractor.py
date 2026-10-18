from datetime import date
from decimal import Decimal as D

import pytest

from app.extractor import _fake, confidence, ground, value
from app.ocr import ocr_pdf
from app.samples import Package, build

PKG = Package(vendor="CV Sinar Konstruksi", npwp="02.345.678.9-012.000", invoice_no="INV/SK/2026/031",
              contract_no="SPK/SLO/2026/002", tanggal="12-10-2026", progres_klaim="60",
              line_items=[("Pekerjaan Struktur", 180_000_000), ("Pekerjaan Atap", 120_000_000)],
              ppn=33_000_000, bruto=333_000_000, progres_bap="55", tanggal_bap="12-10-2026", proyek="Cluster C1",
              pph=("1,75", 5_250_000),
              faktur={"nsfp": "010.000-26.00012345", "npwp": "02.345.678.9-012.000", "dpp": 300_000_000,
                      "ppn": 33_000_000})


@pytest.fixture(scope="module", params=[False, True], ids=["digital", "scan"])
def pages(request, tmp_path_factory):
    return ocr_pdf(build(PKG, tmp_path_factory.mktemp("pdf") / "p.pdf", raster=request.param))


def test_fake_extract_semua_field(pages):
    ext = ground(_fake(pages), pages)
    assert ext["page_types"] == {1: "INVOICE", 2: "BAP", 3: "FAKTUR_PAJAK", 4: "FOTO_PROGRES"}
    assert value(ext, "invoice_no") == "INVSK2026031"
    assert value(ext, "npwp") == "0023456789012000"
    assert value(ext, "contract_no") == "SPKSLO2026002"
    assert value(ext, "progres_klaim") == 60 and value(ext, "progres_bap") == 55
    assert value(ext, "tanggal_bap") == date(2026, 10, 12)
    assert value(ext, "bruto_tertulis") == 333_000_000 and value(ext, "ppn_tertulis") == 33_000_000
    assert value(ext, "pph_tertulis_rate") == D("1.75")
    assert value(ext, "retensi_tertulis") is None  # tidak tercantum -> null sah
    assert value(ext, "faktur_ppn") == 33_000_000
    assert [f["value"] for f in ext["line_items"]] == ["Rp180.000.000", "Rp120.000.000"]
    assert confidence(ext) >= D("0.85")


def test_grounding_menolak_nilai_karangan(pages):
    ext = _fake(pages)
    ext["fields"]["progres_bap"]["value"] = "80"  # AI "mengarang"
    ext = ground(ext, pages)
    assert ext["fields"]["progres_bap"]["confidence"] == 0
    assert value(ext, "progres_bap") is None
    assert confidence(ext) == 0


def test_jalur_gemini_dengan_client_tiruan(pages, monkeypatch):
    """Pemetaan respons Gemini -> format internal, tanpa jaringan."""
    from google import genai

    from app import extractor as ex

    truth = ex._fake(pages)
    out = ex.ExtractionOut(
        page_types=[ex.PageTypeOut(page=k, type=v) for k, v in truth["page_types"].items()],
        line_items=[ex.FieldOut(**f) for f in truth["line_items"]], progres_inkremental=False,
        **{n: ex.FieldOut(**truth["fields"][n]) for n in ex.WAJIB + ex.OPSIONAL})

    class Resp:
        parsed = out
        text = out.model_dump_json()

    class Models:
        def generate_content(self, **kw):
            assert kw["config"].response_schema is ex.ExtractionOut
            return Resp()

    class FakeClient:
        def __init__(self, **kw):
            self.models = Models()

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setenv("GEMINI_MODE", "gemini")
    ext = ex.extract(pages)
    assert ext["mode"] == "gemini"
    assert value(ext, "progres_bap") == 55 and value(ext, "bruto_tertulis") == 333_000_000
    assert confidence(ext) >= D("0.85")


def test_kuota_habis_tidak_diulang(pages, monkeypatch):
    from google import genai

    from app import extractor as ex
    calls = []

    class Models:
        def generate_content(self, **kw):
            calls.append(1)
            raise Exception("429 RESOURCE_EXHAUSTED quota")

    class FakeClient:
        def __init__(self, **kw):
            self.models = Models()

    monkeypatch.setattr(genai, "Client", FakeClient)
    with pytest.raises(RuntimeError, match="Gemini quota exhausted"):
        ex._gemini(pages)
    assert len(calls) == 1  # tidak membuang kuota dengan mengulang
