"""Parser Agent (FR-5): klasifikasi halaman + ekstraksi field, lalu grounding ke kata OCR.

Mode:
- gemini: Google Gemini (AI Studio via GEMINI_API_KEY, atau Vertex via GOOGLE_GENAI_USE_VERTEXAI).
- fake:   pola teks deterministik — untuk tes, demo offline, dan cadangan bila internet mati.
"""
import json
import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, Optional

from pydantic import BaseModel

from app.audit import norm_npwp

WAJIB = ["invoice_no", "npwp", "contract_no", "progres_klaim", "progres_bap", "tanggal_bap", "bruto_tertulis"]
OPSIONAL = ["ppn_tertulis", "retensi_tertulis", "pph_tertulis_rate",
            "faktur_nsfp", "faktur_npwp", "faktur_dpp", "faktur_ppn"]
KIND = {"invoice_no": "text", "contract_no": "text", "faktur_nsfp": "text", "npwp": "npwp", "faktur_npwp": "npwp",
        "progres_klaim": "pct", "progres_bap": "pct", "pph_tertulis_rate": "pct", "tanggal_bap": "date",
        "bruto_tertulis": "money", "ppn_tertulis": "money", "retensi_tertulis": "money", "faktur_dpp": "money",
        "faktur_ppn": "money", "line_item": "money"}
BULAN = {"JANUARI": 1, "FEBRUARI": 2, "MARET": 3, "APRIL": 4, "MEI": 5, "JUNI": 6, "JULI": 7, "AGUSTUS": 8,
         "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11, "DESEMBER": 12}


def mode() -> str:
    m = os.getenv("GEMINI_MODE", "auto")
    if m != "auto":
        return m
    has_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
    return "gemini" if has_key else "fake"


# ---------- normalisasi nilai (dipakai grounding & konversi) ----------

def parse(kind: str, s: str | None):
    if s is None or str(s).strip() == "":
        return None
    s = str(s).strip()
    try:
        if kind == "money":
            neg = s.startswith(("-", "(")) or s.startswith("Rp-")  # potongan: "(Rp300.000.000)" / "-300000000"
            d = re.sub(r",\d{1,2}\)?$", "", s)  # buang sen ",00"
            d = re.sub(r"\D", "", d)
            return (-int(d) if neg else int(d)) if d else None
        if kind == "pct":
            m = re.search(r"\d+(?:[.,]\d+)?", s)
            return Decimal(m.group().replace(",", ".")) if m else None
        if kind == "npwp":
            return norm_npwp(s) or None
        if kind == "date":
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
            if m:
                return date(int(m[1]), int(m[2]), int(m[3]))
            m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s)
            if m:
                return date(int(m[3]), int(m[2]), int(m[1]))
            m = re.search(r"(\d{1,2})\s*([A-Za-z]+)\s*(\d{4})", s)  # OCR scan bisa menempel: "14Oktober2026"
            if m and m[2].upper() in BULAN:
                return date(int(m[3]), BULAN[m[2].upper()], int(m[1]))
            return None
        return re.sub(r"[^A-Z0-9]", "", s.upper()) or None
    except (ValueError, InvalidOperation):
        return None


def ground(ext: dict, pages: list[dict]) -> dict:
    """Paksa confidence 0 bila nilai tidak benar-benar ada di kata OCR yang dirujuk."""
    words = {w["id"]: w for p in pages for w in p["words"]}

    def check(kind, f):
        if f.get("value") in (None, ""):
            f["confidence"] = 0.0
            f["grounded"] = False
            return
        txt = " ".join(words[i]["text"] for i in f.get("word_ids", []) if i in words)
        a, b = parse(kind, txt), parse(kind, f["value"])
        if kind == "money" and a is not None and b is not None:
            a, b = abs(a), abs(b)  # tanda potongan bisa ada di kurung, bukan di kata yang dirujuk
        ok = bool(txt) and b is not None and a == b
        if not ok and b is not None and kind in ("text", "npwp", "money"):
            # OCR scan bisa menempelkan label dan nilai dalam satu kata ("Pajak:0400...")
            hay = re.sub(r"\D", "", txt) if kind != "text" else re.sub(r"[^A-Z0-9]", "", txt.upper())
            needle = str(b) if kind == "money" else b
            ok = len(needle) >= 4 and needle in hay
        f["grounded"] = ok
        if not ok:
            f["confidence"] = 0.0

    for name, f in ext["fields"].items():
        check(KIND[name], f)
    for f in ext["line_items"]:
        check("money", f)
    return ext


def confidence(ext: dict) -> Decimal:
    return min(Decimal(str(ext["fields"].get(n, {}).get("confidence", 0))) for n in WAJIB).quantize(Decimal("0.01"))


# ---------- fake extractor ----------

def _reading_order(words: list[dict]) -> list[dict]:
    """Susun kata per baris visual (pusat vertikal berdekatan), atas ke bawah, kiri ke kanan."""
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["bbox"][1] + w["bbox"][3]) / 2):
        cy, h = (w["bbox"][1] + w["bbox"][3]) / 2, w["bbox"][3] - w["bbox"][1]
        if lines and abs(lines[-1][0]["_cy"] - cy) < max(2.0, 0.35 * h):
            lines[-1].append({**w, "_cy": lines[-1][0]["_cy"]})
        else:
            lines.append([{**w, "_cy": cy}])
    return [w for line in lines for w in sorted(line, key=lambda w: w["bbox"][0])]


def _page_text(page):
    spans, parts, pos = [], [], 0
    for w in _reading_order(page["words"]):
        spans.append((pos, pos + len(w["text"]), w))
        parts.append(w["text"])
        pos += len(w["text"]) + 1
    return " ".join(parts), spans


def _find(page, pattern, flags=re.I):
    text, spans = _page_text(page)
    m = re.search(pattern, text, flags)
    if not m:
        return None
    a, b = m.span("v")
    ws = [w for s, e, w in spans if s < b and e > a]
    return {"value": m.group("v"), "word_ids": [w["id"] for w in ws],
            "confidence": round(min(w.get("conf", 1.0) for w in ws) * 0.97, 2)}


def _classify(page) -> str:
    t = "".join(w["text"] for w in page["words"]).upper()  # tanpa spasi: OCR scan kadang menempelkan kata
    keys = [("BERITAACARA", "BAP"), ("FAKTURPAJAK", "FAKTUR_PAJAK"), ("LAPORANFOTO", "FOTO_PROGRES"),
            ("FOTOPROGRES", "FOTO_PROGRES"), ("INVOICE", "INVOICE")]
    hits = [(t.find(k), typ) for k, typ in keys if k in t]
    return min(hits)[1] if hits else "LAIN"  # judul halaman = kata kunci paling awal


MONEY = r"Rp\s?[\d.]+(?:,\d{2})?"
PATTERNS = {
    "INVOICE": {
        "invoice_no": r"(?:No\.?|Nomor)\s*(?:Invoice|Tagihan)\s*:?\s*(?P<v>[^\s:]\S*)",
        "npwp": r"NPWP\s*:?\s*(?P<v>[\d.\-]{15,22})",
        "contract_no": r"(?:No\.?|Nomor)\s*(?:Kontrak|SPK)(?:\s*/\s*SPK)?\s*:?\s*(?P<v>[^\s:]\S*)",
        "progres_klaim": r"Progres\s*Kumulatif[^:%]*:\s*(?P<v>\d+(?:[.,]\d+)?\s?%)",
        "bruto_tertulis": rf"(?:(?:Total|Jumlah)\s*Tagihan|Grand\s*Total)[^:]*:\s*(?P<v>{MONEY})",
        "ppn_tertulis": rf"PPN\s*\(?\s*11\s?%\s*\)?\s*:?\s*(?P<v>{MONEY})",
        "retensi_tertulis": rf"Retensi[^:]*:\s*\(?\s*(?P<v>{MONEY})",
        "pph_tertulis_rate": r"PPh\s*(?:Pasal\s*|Ps\.\s*)?4\s*(?:ayat\s*)?\(2\)\s*(?P<v>\d+(?:,\d+)?\s?%?)",
    },
    "BAP": {
        "progres_bap": r"Progres\s*Fisik\s*Kumulatif[^:%]*:\s*(?P<v>\d+(?:[.,]\d+)?\s?%)",
        "tanggal_bap": r"Tanggal\s*Pemeriksaan\s*:?\s*(?P<v>\d{1,2}(?:[-/.]\d{1,2}[-/.]|\s*[A-Za-z]+\s*)\d{4})",
    },
    "FAKTUR_PAJAK": {
        "faktur_nsfp": r"Nomor\s*Seri\s*Faktur(?:\s*Pajak)?\s*:?\s*(?P<v>\d[\d.\-]+)",
        "faktur_npwp": r"NPWP\s*(?:Penjual)?\s*:?\s*(?P<v>[\d.\-]{15,22})",
        "faktur_dpp": rf"Dasar\s*Pengenaan\s*Pajak[^:]*:\s*(?P<v>{MONEY})",
        "faktur_ppn": rf"(?:Total\s*PPN[^:]*|(?<![\w])PPN):\s*(?P<v>{MONEY})",
    },
}


def _fake(pages: list[dict]) -> dict:
    types = {p["n"]: _classify(p) for p in pages}
    fields = {n: {"value": None, "word_ids": [], "confidence": 0.0} for n in WAJIB + OPSIONAL}
    items = []
    for p in pages:
        for name, pat in PATTERNS.get(types[p["n"]], {}).items():
            if fields[name]["value"] is None and (hit := _find(p, pat)):
                fields[name] = hit
        if types[p["n"]] == "INVOICE":
            text, spans = _page_text(p)
            start = re.search(r"Jumlah", text)
            end = re.search(r"PPN\s*11%", text)
            if start and end:
                prev = start.end()
                for m in re.finditer(MONEY, text[start.end():end.start()]):
                    a, b = m.start() + start.end(), m.end() + start.end()
                    label, prev = text[prev:a], b
                    if re.search(r"total|jumlah|dpp", label, re.I):  # baris subtotal, bukan rincian
                        continue
                    ws = [w for s, e, w in spans if s < b and e > a]
                    sign = "-" if text[a - 1:a] == "(" else ""
                    items.append({"value": sign + m.group(), "word_ids": [w["id"] for w in ws],
                                  "confidence": round(min(w.get("conf", 1.0) for w in ws) * 0.97, 2)})
    return {"mode": "fake", "model": "pola-teks", "page_types": types, "fields": fields, "line_items": items,
            "inkremental": False}


# ---------- Gemini extractor ----------

class FieldOut(BaseModel):
    value: Optional[str]
    word_ids: list[str]
    confidence: float


class PageTypeOut(BaseModel):
    page: int
    type: Literal["INVOICE", "BAP", "FAKTUR_PAJAK", "FOTO_PROGRES", "LAIN"]


class ExtractionOut(BaseModel):
    page_types: list[PageTypeOut]
    invoice_no: FieldOut
    npwp: FieldOut
    contract_no: FieldOut
    progres_klaim: FieldOut
    progres_bap: FieldOut
    tanggal_bap: FieldOut
    bruto_tertulis: FieldOut
    ppn_tertulis: FieldOut
    retensi_tertulis: FieldOut
    pph_tertulis_rate: FieldOut
    faktur_nsfp: FieldOut
    faktur_npwp: FieldOut
    faktur_dpp: FieldOut
    faktur_ppn: FieldOut
    line_items: list[FieldOut]
    progres_inkremental: bool


PROMPT = """Anda adalah Parser Agent untuk audit tagihan kontraktor developer properti di Indonesia.
Input adalah kata-kata hasil OCR, setiap kata diberi ID (format ID:teks), dikelompokkan per halaman dan per baris.

Tugas:
1. Klasifikasikan setiap halaman: INVOICE, BAP (Berita Acara Pemeriksaan), FAKTUR_PAJAK, FOTO_PROGRES, atau LAIN.
2. Ekstrak field berikut. Untuk setiap field berikan value, word_ids (ID kata yang PERSIS memuat nilai itu saja,
   tanpa kata label), dan confidence 0..1. Jika field tidak ada di dokumen: value null, word_ids [], confidence 0.
   JANGAN mengarang nilai. JANGAN menghitung apa pun; hanya baca.
   - invoice_no, contract_no: teks apa adanya
   - npwp: NPWP vendor di invoice (teks apa adanya)
   - progres_klaim: persen progres KUMULATIF yang ditagih di invoice, angka saja (mis. "60")
   - progres_bap: persen progres fisik KUMULATIF di BAP, angka saja
   - tanggal_bap: tanggal pemeriksaan BAP, format YYYY-MM-DD
   - bruto_tertulis: total tagihan termasuk PPN di invoice, angka rupiah tanpa titik (mis. "333000000")
   - ppn_tertulis: PPN di invoice; retensi_tertulis: retensi di invoice; pph_tertulis_rate: tarif PPh 4(2) di invoice (angka persen)
   - faktur_nsfp, faktur_npwp, faktur_dpp, faktur_ppn: dari halaman Faktur Pajak
   - line_items: setiap nilai rupiah rincian pekerjaan (sebelum PPN) di invoice, TIDAK termasuk baris subtotal/total;
     potongan (mis. pengembalian uang muka, ditulis dalam kurung) diberi tanda minus, mis. "-300000000"
3. progres_inkremental = true jika invoice menyebut progres termin ini saja (bukan kumulatif).

Dokumen:
"""


def _lines(page) -> str:
    rows: list[list[dict]] = []
    for w in sorted(page["words"], key=lambda w: (round(w["bbox"][1] / 6), w["bbox"][0])):
        if rows and abs(rows[-1][0]["bbox"][1] - w["bbox"][1]) < 6:
            rows[-1].append(w)
        else:
            rows.append([w])
    return "\n".join(" ".join(f'{w["id"]}:{w["text"]}' for w in r) for r in rows)


def _gemini(pages: list[dict]) -> dict:
    from google import genai
    from google.genai import types

    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    client = genai.Client(http_options=types.HttpOptions(timeout=90_000))
    doc = "\n\n".join(f"=== Halaman {p['n']} ===\n{_lines(p)}" for p in pages)
    last_err = None
    for _ in range(2):  # FR: ulang 1x
        try:
            resp = client.models.generate_content(
                model=model, contents=PROMPT + doc,
                config=types.GenerateContentConfig(response_mime_type="application/json",
                                                   response_schema=ExtractionOut, temperature=0))
            out = resp.parsed if isinstance(resp.parsed, ExtractionOut) else ExtractionOut.model_validate_json(resp.text)
            data = out.model_dump()
            return {"mode": "gemini", "model": model,
                    "page_types": {pt["page"]: pt["type"] for pt in data["page_types"]},
                    "fields": {n: data[n] for n in WAJIB + OPSIONAL},
                    "line_items": data["line_items"], "inkremental": data["progres_inkremental"]}
        except Exception as e:  # noqa: BLE001
            last_err = e
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                raise RuntimeError("Kuota Gemini habis (429). Coba lagi nanti, ganti GEMINI_MODEL, atau pakai key berbayar.")
    raise RuntimeError(f"Gemini gagal: {str(last_err)[:300]}")


def extract(pages: list[dict]) -> dict:
    ext = _gemini(pages) if mode() == "gemini" else _fake(pages)
    ext["page_types"] = {int(k): v for k, v in ext["page_types"].items()}
    return ground(ext, pages)


def extract_offline(pages: list[dict], reason: str) -> dict:
    """Cadangan saat Gemini tidak tersedia (kuota/jaringan): pola teks lokal, alasan dicatat."""
    ext = _fake(pages)
    ext["fallback_reason"] = reason
    return ground(ext, pages)


def value(ext: dict, name: str):
    """Nilai field ter-parse; field ber-confidence 0 dianggap tidak ada."""
    f = ext["fields"].get(name) or {}
    v = parse(KIND[name], f.get("value")) if f.get("grounded") else None
    return abs(v) if KIND[name] == "money" and v is not None else v


def dumps(ext: dict) -> str:
    return json.dumps(ext, default=str)
