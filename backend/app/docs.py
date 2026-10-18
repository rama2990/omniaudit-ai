"""Generator dokumen tagihan kontraktor yang realistis untuk simulasi full run.

Tiga gaya vendor (KORPORAT, CV, MENENGAH) dengan label, format tanggal, dan tata letak berbeda,
BAP bertabel bobot pekerjaan, Faktur Pajak format Coretax (PPN 12% x DPP Nilai Lain 11/12),
dan halaman foto progres. Opsi `scan` meraster semua halaman + noise agar jalur OCR teruji.
Semua nama, NPWP, dan alamat fiktif.
"""
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pymupdf
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

W, H = A4
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
         "November", "Desember"]
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def idr(n: int) -> str:
    s = "Rp" + f"{abs(n):,}".replace(",", ".")
    return f"({s})" if n < 0 else s


def pct(p: str) -> str:
    return p.replace(".", ",") + "%"


def tgl_panjang(d: date) -> str:
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def terbilang(n: int) -> str:
    satuan = ["", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"]

    def t(x: int) -> str:
        if x < 12:
            return satuan[x]
        if x < 20:
            return t(x - 10) + " belas"
        if x < 100:
            return t(x // 10) + " puluh " + t(x % 10)
        if x < 200:
            return "seratus " + t(x - 100)
        if x < 1000:
            return t(x // 100) + " ratus " + t(x % 100)
        if x < 2000:
            return "seribu " + t(x - 1000)
        for div, word in [(10**12, "triliun"), (10**9, "miliar"), (10**6, "juta"), (1000, "ribu")]:
            if x >= div:
                return t(x // div) + f" {word} " + t(x % div)
        return ""

    words = " ".join(t(n).split())
    return (words[:1].upper() + words[1:] + " rupiah") if n else "Nol rupiah"


@dataclass
class Party:
    name: str
    npwp: str  # format tampilan
    address: str
    tagline: str = ""
    bank: str = ""
    signer: str = ""
    signer_title: str = "Direktur"


@dataclass
class TerminDoc:
    style: str  # KORPORAT | CV | MENENGAH
    vendor: Party
    buyer: Party
    invoice_no: str
    contract_ref: str  # sebagaimana ditulis vendor
    tanggal: date
    proyek: str
    termin_label: str
    progres: str  # "60" kumulatif, atau progres termin ini bila inkremental
    items: list  # [(uraian, jumlah, keterangan)] jumlah negatif = potongan
    ppn: int
    bruto: int
    bap_progres: str
    bap_tanggal: date
    inkremental: bool = False
    retensi: int | None = None
    pph: tuple | None = None  # ("1,75", 5250000)
    faktur: dict | None = None  # {nsfp, harga, um, ppn}
    photos: list = field(default_factory=list)
    scan: bool = False


# ---------- elemen gambar ----------

def stamp(c: Canvas, x, y, text, color="#1a3c8f"):
    c.saveState()
    col = HexColor(color)
    c.setStrokeColor(col)
    c.setFillColor(col)
    c.setLineWidth(1.6)
    c.circle(x, y, 34, stroke=1, fill=0)
    c.circle(x, y, 28, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(x, y + 4, text[:22])
    c.drawCentredString(x, y - 6, "* JAKARTA *")
    c.restoreState()


def signature(c: Canvas, x, y, seed: int):
    c.saveState()
    c.setStrokeColor(HexColor("#22305e"))
    c.setLineWidth(1.1)
    rng = np.random.default_rng(seed)
    p = c.beginPath()
    p.moveTo(x, y)
    for i in range(6):
        p.curveTo(x + 10 + i * 14, y + rng.uniform(5, 18), x + 16 + i * 14, y - rng.uniform(4, 12), x + 22 + i * 14,
                  y + rng.uniform(-3, 6))
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def materai(c: Canvas, x, y):
    c.saveState()
    c.setFillColor(HexColor("#f6e7f0"))
    c.setStrokeColor(HexColor("#b5477d"))
    c.rect(x, y, 46, 34, fill=1, stroke=1)
    c.setFillColor(HexColor("#b5477d"))
    c.setFont("Helvetica-Bold", 5.5)
    c.drawCentredString(x + 23, y + 23, "METERAI")
    c.drawCentredString(x + 23, y + 15, "TEMPEL")
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(x + 23, y + 5, "10000")
    c.restoreState()


def kv(c: Canvas, x, y, rows, x2, size=10, bold_value=True, gap=15):
    for label, value in rows:
        c.setFont("Helvetica", size)
        c.drawString(x, y, label)
        c.drawString(x2 - 10, y, ":")
        c.setFont("Helvetica-Bold" if bold_value else "Helvetica", size)
        c.drawString(x2, y, value)
        y -= gap
    return y


def table(c: Canvas, x, y, widths, header, rows, size=9, align=None, head_fill="#e8eaed", row_h=17):
    align = align or ["L"] * len(widths)
    total_w = sum(widths)
    c.setFillColor(HexColor(head_fill))
    c.rect(x, y - row_h + 4, total_w, row_h, fill=1, stroke=0)
    c.setFillColor(HexColor("#202124"))

    def row(vals, yy, font):
        cx = x
        c.setFont(font, size)
        for v, w, a in zip(vals, widths, align):
            if a == "R":
                c.drawRightString(cx + w - 4, yy, v)
            elif a == "C":
                c.drawCentredString(cx + w / 2, yy, v)
            else:
                c.drawString(cx + 4, yy, v)
            cx += w

    row(header, y - 8, "Helvetica-Bold")
    yy = y - row_h
    c.setLineWidth(0.5)
    c.setStrokeColor(HexColor("#9aa0a6"))
    for r in rows:
        row(r, yy - 8, "Helvetica")
        yy -= row_h
    c.rect(x, yy + 4, total_w, y - yy, fill=0, stroke=1)
    cx = x
    for w in widths[:-1]:
        cx += w
        c.line(cx, y + 4, cx, yy + 4)
    return yy


# ---------- halaman ----------

def _letterhead(c: Canvas, d: TerminDoc):
    v = d.vendor
    if d.style == "KORPORAT":
        c.setFillColor(HexColor("#0b3d91"))
        c.rect(40, H - 92, 56, 56, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(68, H - 72, "".join(w[0] for w in v.name.split()[1:4]))
        c.setFillColor(HexColor("#0b3d91"))
        c.setFont("Helvetica-Bold", 16)
        c.drawString(108, H - 55, v.name.upper())
        c.setFillColor(HexColor("#5f6368"))
        c.setFont("Helvetica", 8.5)
        c.drawString(108, H - 69, v.tagline)
        c.drawString(108, H - 81, v.address)
        c.drawString(108, H - 93, f"NPWP: {v.npwp}")
        c.setStrokeColor(HexColor("#0b3d91"))
        c.setLineWidth(2)
        c.line(40, H - 104, W - 40, H - 104)
        c.setFillColor(HexColor("#202124"))
        c.setFont("Helvetica-Bold", 20)
        c.drawRightString(W - 40, H - 140, "INVOICE")
        return H - 130
    if d.style == "CV":
        c.setFont("Helvetica-Bold", 15)
        c.drawString(40, H - 55, v.name.upper())
        c.setFont("Helvetica", 9)
        c.drawString(40, H - 69, v.tagline)
        c.drawString(40, H - 81, v.address)
        c.line(40, H - 90, W - 40, H - 90)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(W / 2, H - 120, "INVOICE")
        return H - 145
    # MENENGAH
    c.setFillColor(HexColor("#0f766e"))
    c.rect(0, H - 80, W, 80, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(40, H - 38, v.name.upper())
    c.setFont("Helvetica", 8.5)
    c.drawString(40, H - 53, v.tagline + "  |  " + v.address)
    c.setFont("Helvetica-Bold", 17)
    c.drawRightString(W - 40, H - 40, "TAGIHAN / INVOICE")
    c.setFillColor(HexColor("#202124"))
    return H - 110


def page_invoice(c: Canvas, d: TerminDoc):
    y = _letterhead(c, d)
    v, b = d.vendor, d.buyer
    if d.style == "KORPORAT":
        label_inv, label_kon, tanggal = "Nomor Invoice", "Nomor Kontrak/SPK", tgl_panjang(d.tanggal)
        label_prog = "Progres termin ini" if d.inkremental else "Progres kumulatif s.d. termin ini"
    elif d.style == "CV":
        label_inv, label_kon, tanggal = "No. Invoice", "No. Kontrak", d.tanggal.strftime("%d-%m-%Y")
        label_prog = "Progres termin ini" if d.inkremental else "Progres Kumulatif Ditagih"
    else:
        label_inv, label_kon, tanggal = "Nomor Tagihan", "No. SPK", d.tanggal.strftime("%d/%m/%Y")
        label_prog = "Progres termin ini" if d.inkremental else "Progres Kumulatif s.d. Termin Ini"
    rows = [(label_inv, d.invoice_no)]
    if d.style != "KORPORAT":
        rows.append(("NPWP", v.npwp))
    rows += [(label_kon, d.contract_ref), ("Tanggal", tanggal), ("Proyek", d.proyek), ("Termin", d.termin_label),
             (label_prog, pct(d.progres + (",00" if d.style == "KORPORAT" else "")))]
    y = kv(c, 40, y, rows, 210)
    # Kepada: korporat di bawah rincian (nilai proyek panjang), gaya lain di kolom kanan
    bx, by = (40, y - 4) if d.style == "KORPORAT" else (370, y + 15 * len(rows))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(bx, by, "Kepada Yth.")
    c.setFont("Helvetica", 9)
    for line in (b.name, b.address, f"NPWP {b.npwp}"):
        by -= 12
        c.drawString(bx, by, line)
    y = (by - 22) if d.style == "KORPORAT" else (y - 12)
    if d.style == "MENENGAH":
        widths, header = [28, 255, 90, 142], ["No", "Uraian Pekerjaan", "Volume", "Jumlah (Rp)"]
        rows_t = [[str(i + 1), u, k, idr(a)] for i, (u, a, k) in enumerate(d.items)]
        rows_t.append(["", "Sub Total", "", idr(sum(a for _, a, _ in d.items))])
        y = table(c, 40, y, widths, header, rows_t, align=["C", "L", "C", "R"])
    elif d.style == "KORPORAT":
        widths, header = [28, 330, 157], ["No", "Uraian Pekerjaan", "Jumlah (Rp)"]
        rows_t = [[str(i + 1), u, idr(a)] for i, (u, a, _) in enumerate(d.items)]
        y = table(c, 40, y, widths, header, rows_t, align=["C", "L", "R"], head_fill="#dbe4f5")
    else:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, "Uraian Pekerjaan")
        c.drawRightString(W - 40, y, "Jumlah")
        c.line(40, y - 5, W - 40, y - 5)
        y -= 22
        c.setFont("Helvetica", 10)
        for u, a, _ in d.items:
            c.drawString(40, y, u)
            c.drawRightString(W - 40, y, idr(a))
            y -= 18
        c.line(40, y + 8, W - 40, y + 8)
    y -= 14
    x2 = 380
    if d.style == "KORPORAT":
        totals = [("Jumlah sebelum PPN", idr(sum(a for _, a, _ in d.items))), ("PPN 11%", idr(d.ppn)),
                  ("Total Tagihan (termasuk PPN)", idr(d.bruto))]
    elif d.style == "MENENGAH":
        totals = [("PPN 11%", idr(d.ppn)), ("Grand Total", idr(d.bruto))]
    else:
        totals = [("PPN 11%", idr(d.ppn)), ("Total Tagihan", idr(d.bruto))]
    y = kv(c, 200, y, totals, x2)
    if d.style == "KORPORAT":
        c.setFont("Helvetica-Oblique", 8.5)
        c.drawString(40, y - 2, "Terbilang: " + terbilang(d.bruto))
        y -= 20
    ded = []
    if d.retensi is not None:
        ded.append(("Retensi 5% (ditahan)" if d.style != "CV" else "Retensi 5%", idr(-d.retensi) if d.style != "CV" else idr(d.retensi)))
    if d.pph:
        lab = {"KORPORAT": "PPh Pasal 4 ayat (2)", "MENENGAH": "PPh Ps. 4(2)", "CV": "PPh 4(2)"}[d.style]
        ded.append((f"{lab} {d.pph[0]}%", idr(-d.pph[1]) if d.style != "CV" else idr(d.pph[1])))
    if ded:
        y = kv(c, 200, y, ded, x2, bold_value=False)
    if d.style != "CV":
        net = d.bruto - (d.retensi or 0) - (d.pph[1] if d.pph else 0)
        y = kv(c, 200, y, [("Jumlah yang dibayarkan", idr(net))], x2)
    # pembayaran + tanda tangan
    c.setFont("Helvetica", 8.5)
    c.drawString(40, 150, "Pembayaran mohon ditransfer ke:")
    c.drawString(40, 138, v.bank)
    c.drawString(40, 126, "Faktur Pajak dan BAP terlampir.")
    c.setFont("Helvetica", 9)
    c.drawString(400, 160, f"Jakarta, {tgl_panjang(d.tanggal)}")
    c.drawString(400, 148, v.name)
    if d.style == "KORPORAT":
        materai(c, 395, 92)
    stamp(c, 470, 108, v.name.replace("PT ", "").replace("CV ", ""))
    signature(c, 430, 100, seed=len(d.invoice_no))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(400, 70, v.signer)
    c.setFont("Helvetica", 8.5)
    c.drawString(400, 59, v.signer_title)
    c.showPage()


def _bobot(progres: float) -> list[tuple]:
    """Bagi progres kumulatif ke item pekerjaan berbobot; jumlah realisasi = progres."""
    items = [("Pekerjaan persiapan", 5.0), ("Pekerjaan struktur", 45.0), ("Pekerjaan arsitektur", 30.0),
             ("Pekerjaan MEP", 20.0)]
    left, out = progres, []
    for name, w in items:
        real = round(min(w, left), 2)
        left = round(left - real, 2)
        out.append((name, w, real))
    return out


def page_bap(c: Canvas, d: TerminDoc):
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(W / 2, H - 60, "BERITA ACARA PEMERIKSAAN PEKERJAAN")
    c.setFont("Helvetica", 10)
    c.drawCentredString(W / 2, H - 76, f"Nomor: BAP/{d.contract_ref.replace('/', '-')}/{d.bap_tanggal:%m%y}")
    c.line(120, H - 84, W - 120, H - 84)
    c.setFont("Helvetica", 9.5)
    hari = HARI[d.bap_tanggal.weekday()]
    txt = (f"Pada hari ini, {hari} tanggal {tgl_panjang(d.bap_tanggal)}, kami yang bertanda tangan di bawah ini "
           f"telah melakukan pemeriksaan lapangan")
    c.drawString(40, H - 108, txt)
    c.drawString(40, H - 121, f"bersama atas pekerjaan {d.proyek} dengan hasil sebagai berikut.")
    y = kv(c, 40, H - 148, [("Nomor Kontrak", d.contract_ref), ("Pelaksana", d.vendor.name), ("Pemilik", d.buyer.name),
                            ("Tanggal Pemeriksaan", tgl_panjang(d.bap_tanggal))], 190)
    y -= 6
    rows = []
    for name, w, real in _bobot(float(d.bap_progres)):
        prog_item = 0 if w == 0 else real / w * 100
        rows.append([name, f"{w:.2f}".replace(".", ","), f"{prog_item:.1f}".replace(".", ","),
                     f"{real:.2f}".replace(".", ",")])
    rows.append(["Total bobot realisasi kumulatif", "100,00", "", f"{float(d.bap_progres):.2f}".replace(".", ",")])
    y = table(c, 40, y, [235, 90, 95, 95], ["Item Pekerjaan", "Bobot (%)", "Progres item (%)", "Realisasi (%)"], rows,
              align=["L", "R", "R", "R"])
    y -= 22
    kv(c, 40, y, [("Progres Fisik Kumulatif", pct(d.bap_progres + ",00"))], 190, size=11)
    c.setFont("Helvetica", 9)
    c.drawString(40, y - 26, "Demikian berita acara ini dibuat dengan sebenarnya untuk dipergunakan sebagaimana mestinya.")
    for i, (who, role) in enumerate([(d.vendor.signer, "Pelaksana"), ("Ir. Bonifasius Halim", "Konsultan Pengawas"),
                                     ("Yulia Paramitha, S.T.", "Wakil Pemilik Proyek")]):
        x = 50 + i * 180
        c.drawString(x, 190, role)
        signature(c, x, 150, seed=i + 7)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x, 120, who)
        c.setFont("Helvetica", 9)
    stamp(c, 270, 160, "KONSULTAN MK", "#7b1f1f")
    c.showPage()


def page_faktur(c: Canvas, d: TerminDoc):
    f = d.faktur
    base = f["harga"] - f["um"]
    dpp_nl = round(base * 11 / 12)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(W / 2, H - 55, "FAKTUR PAJAK")
    c.setFont("Helvetica", 9.5)
    c.rect(40, H - 90, W - 80, 22, stroke=1, fill=0)
    c.drawString(48, H - 82, f"Kode dan Nomor Seri Faktur Pajak : {f['nsfp']}")
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(40, H - 112, "Pengusaha Kena Pajak")
    y = kv(c, 40, H - 128, [("Nama", d.vendor.name), ("Alamat", d.vendor.address), ("NPWP", d.vendor.npwp)], 120,
           size=9, bold_value=False, gap=13)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(40, y - 6, "Pembeli Barang Kena Pajak / Penerima Jasa Kena Pajak")
    y = kv(c, 40, y - 22, [("Nama", d.buyer.name), ("Alamat", d.buyer.address), ("NPWP", d.buyer.npwp)], 120,
           size=9, bold_value=False, gap=13)
    y -= 8
    rows = [[str(i + 1), u, idr(a)] for i, (u, a, _) in enumerate(d.items) if a > 0]
    y = table(c, 40, y, [28, 352, 135], ["No", "Nama Barang Kena Pajak / Jasa Kena Pajak", "Harga Jual (Rp)"], rows,
              align=["C", "L", "R"])
    y -= 16
    y = kv(c, 150, y, [
        ("Harga Jual / Penggantian / Uang Muka / Termin", idr(f["harga"])),
        ("Dikurangi Potongan Harga", idr(0)),
        ("Dikurangi Uang Muka yang telah diterima", idr(f["um"])),
        ("Dasar Pengenaan Pajak (DPP Nilai Lain 11/12)", idr(dpp_nl)),
        ("Total PPN (12%)", idr(f["ppn"])),
        ("Total PPnBM", idr(0)),
    ], 430, size=9, bold_value=False)
    c.setFont("Helvetica", 8)
    c.drawString(40, 110, "Faktur Pajak ini telah dilaporkan ke Direktorat Jenderal Pajak dan dibuat secara elektronik.")
    c.drawString(40, 99, f"Jakarta, {tgl_panjang(d.tanggal)}   {d.vendor.signer}")
    c.showPage()


def _photo(c: Canvas, x, y, w, h, level: float, seed: int):
    rng = np.random.default_rng(seed)
    c.setFillColor(HexColor("#bcd8f2"))
    c.rect(x, y, w, h, fill=1, stroke=0)
    c.setFillColor(HexColor("#a1887f"))
    c.rect(x, y, w, h * 0.22, fill=1, stroke=0)
    floors = max(1, int(level * 8))
    bx, by, bw = x + w * 0.18, y + h * 0.22, w * 0.5
    c.setStrokeColor(HexColor("#616161"))
    c.setLineWidth(2)
    fh = h * 0.08
    for f in range(floors):
        yy = by + f * fh
        c.setFillColor(HexColor("#9e9e9e") if f < floors - 1 else HexColor("#cfd8dc"))
        c.rect(bx, yy, bw, fh * 0.25, fill=1, stroke=0)
        for k in range(5):
            c.line(bx + k * bw / 4, yy, bx + k * bw / 4, yy + fh)
    # crane
    c.setStrokeColor(HexColor("#f9a825"))
    c.setLineWidth(3)
    cx = x + w * 0.82
    c.line(cx, y + h * 0.22, cx, y + h * 0.9)
    c.line(cx - w * 0.45, y + h * 0.9, cx + w * 0.1, y + h * 0.9)
    c.setFillColor(Color(1, 1, 1, alpha=0.6))
    for _ in range(3):
        c.circle(x + rng.uniform(0.1, 0.6) * w, y + h * rng.uniform(0.75, 0.92), rng.uniform(6, 12), fill=1, stroke=0)


def page_foto(c: Canvas, d: TerminDoc):
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, H - 55, "LAPORAN FOTO PROGRES")
    c.setFont("Helvetica", 9.5)
    c.drawString(40, H - 70, f"{d.proyek}  |  Periode s.d. {tgl_panjang(d.bap_tanggal)}")
    level = float(d.bap_progres) / 100
    caps = d.photos or ["Kondisi umum lapangan", "Pekerjaan struktur", "Pekerjaan pembesian", "Pekerjaan bekisting"]
    for i, (x, y) in enumerate([(40, 430), (310, 430), (40, 160), (310, 160)]):
        _photo(c, x, y, 245, 220, min(1.0, level + (i - 1.5) * 0.04), seed=i + len(d.invoice_no))
        c.setFillColor(HexColor("#202124"))
        c.setFont("Helvetica", 8.5)
        c.drawString(x, y - 13, f"Foto {i + 1}. {caps[i % len(caps)]}")
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica", 7)
        c.drawRightString(x + 240, y + 5, f"{d.bap_tanggal:%d/%m/%Y} 10:{12 + i * 7:02d}  -6.2{i}1, 106.6{i}3")
    c.showPage()


def build_doc(d: TerminDoc, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(path), pagesize=A4, invariant=1)
    c.setTitle(f"{d.invoice_no} {d.vendor.name}")
    page_invoice(c, d)
    page_bap(c, d)
    if d.faktur:
        page_faktur(c, d)
    page_foto(c, d)
    c.save()
    if d.scan:
        _scanify(path, seed=len(d.invoice_no))
    return path


def _scanify(path: Path, seed: int):
    """Raster + abu-abu + noise ringan: meniru hasil scanner kantor."""
    rng = np.random.default_rng(seed)
    src = pymupdf.open(path)
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
        a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(np.int16)
        a = a * 0.93 + 8 + rng.normal(0, 7, a.shape)
        a = np.clip(a, 0, 255).astype(np.uint8)
        g = pymupdf.Pixmap(pymupdf.csGRAY, pix.width, pix.height, a.tobytes(), False)
        p = out.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, stream=g.tobytes(output="jpg", jpg_quality=70))
    src.close()
    out.save(path, garbage=3, deflate=True)
    out.close()
