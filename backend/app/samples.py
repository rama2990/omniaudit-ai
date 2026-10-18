"""Generator Paket Dokumen AP contoh (invoice, BAP, faktur pajak, foto progres)."""
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas


def idr(n: int) -> str:
    return "Rp" + f"{n:,}".replace(",", ".")


def pct(p: str) -> str:
    return p.replace(".", ",") + "%"


@dataclass
class Package:
    vendor: str
    npwp: str
    invoice_no: str
    contract_no: str
    tanggal: str  # dd-mm-yyyy
    progres_klaim: str  # "60"
    line_items: list[tuple[str, int]]
    ppn: int
    bruto: int
    progres_bap: str
    tanggal_bap: str
    proyek: str
    retensi: int | None = None
    pph: tuple[str, int] | None = None  # ("1,75", 5250000)
    faktur: dict | None = field(default=None)  # {nsfp, npwp, dpp, ppn}


def _header(c: Canvas, title: str, sub: str):
    w, h = A4
    c.setFillColor(HexColor("#1a73e8"))
    c.rect(0, h - 70, w, 70, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, h - 45, title)
    c.setFont("Helvetica", 10)
    c.drawString(40, h - 62, sub)
    c.setFillColor(HexColor("#202124"))


def _rows(c: Canvas, y: float, rows: list[tuple[str, str]], x2=230, size=11) -> float:
    for label, value in rows:
        c.setFont("Helvetica", size)
        c.drawString(40, y, label)
        c.setFont("Helvetica-Bold", size)
        c.drawString(x2, y, value)
        y -= 20
    return y


def build(pkg: Package, path: Path, raster: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(path), pagesize=A4)
    w, h = A4

    # 1. Invoice
    _header(c, "INVOICE", pkg.vendor)
    y = _rows(c, h - 110, [
        ("No. Invoice:", pkg.invoice_no), ("NPWP:", pkg.npwp), ("No. Kontrak:", pkg.contract_no),
        ("Proyek:", pkg.proyek), ("Tanggal:", pkg.tanggal), ("Progres Kumulatif Ditagih:", pct(pkg.progres_klaim)),
    ])
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Uraian Pekerjaan")
    c.drawRightString(w - 40, y, "Jumlah")
    c.line(40, y - 5, w - 40, y - 5)
    y -= 25
    c.setFont("Helvetica", 11)
    for desc, amt in pkg.line_items:
        c.drawString(40, y, desc)
        c.drawRightString(w - 40, y, idr(amt))
        y -= 20
    c.line(40, y + 10, w - 40, y + 10)
    y -= 5
    rows = [("PPN 11%:", idr(pkg.ppn)), ("Total Tagihan:", idr(pkg.bruto))]
    if pkg.retensi is not None:
        rows.append(("Retensi 5%:", idr(pkg.retensi)))
    if pkg.pph:
        rows.append((f"PPh 4(2) {pkg.pph[0]}%:", idr(pkg.pph[1])))
    _rows(c, y, rows, x2=330)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(40, 60, "Pembayaran ke rekening vendor sesuai kontrak. Dokumen ini dibuat untuk demo OmniAudit AI.")
    c.showPage()

    # 2. BAP
    _header(c, "BERITA ACARA PEMERIKSAAN PEKERJAAN", pkg.proyek)
    y = _rows(c, h - 110, [
        ("No. Kontrak:", pkg.contract_no), ("Pelaksana:", pkg.vendor), ("Tanggal Pemeriksaan:", pkg.tanggal_bap),
        ("Progres Fisik Kumulatif:", pct(pkg.progres_bap)),
    ])
    c.setFont("Helvetica", 11)
    c.drawString(40, y - 10, "Telah dilakukan pemeriksaan lapangan bersama oleh Konsultan Pengawas dan Pemilik Proyek.")
    c.drawString(40, y - 40, "Pengawas Lapangan")
    c.drawString(330, y - 40, "Wakil Pemilik Proyek")
    c.showPage()

    # 3. Faktur Pajak
    if pkg.faktur:
        f = pkg.faktur
        _header(c, "FAKTUR PAJAK", "Pengusaha Kena Pajak: " + pkg.vendor)
        _rows(c, h - 110, [
            ("Nomor Seri Faktur:", f["nsfp"]), ("NPWP Penjual:", f["npwp"]),
            ("Dasar Pengenaan Pajak:", idr(f["dpp"])), ("PPN:", idr(f["ppn"])),
        ])
        c.showPage()

    # 4. Foto progres
    _header(c, "LAPORAN FOTO PROGRES", pkg.proyek)
    for i, (x, yy) in enumerate([(40, 420), (310, 420), (40, 150), (310, 150)]):
        c.setFillColor(HexColor(["#a8c7fa", "#c4eed0", "#fde293", "#f6aea9"][i]))
        c.rect(x, yy, 245, 220, fill=1, stroke=0)
        c.setFillColor(HexColor("#5f6368"))
        c.rect(x + 40, yy + 30, 165, 110, fill=1, stroke=0)
        c.setFillColor(HexColor("#202124"))
        c.setFont("Helvetica", 9)
        c.drawString(x, yy - 14, f"Foto {i + 1}")
    c.showPage()
    c.save()

    if raster:  # simulasi dokumen hasil scan: semua halaman jadi gambar
        src = pymupdf.open(path)
        out = pymupdf.open()
        for page in src:
            pix = page.get_pixmap(dpi=150)
            p = out.new_page(width=page.rect.width, height=page.rect.height)
            p.insert_image(p.rect, stream=pix.tobytes(output="jpg", jpg_quality=80))
        src.close()
        out.save(path)
        out.close()
    return path
