"""Integrasi tiruan: ERP, kuitansi PDF, dan Outbox WhatsApp/email. Tidak ada yang benar-benar terkirim."""
import secrets
from datetime import datetime

from reportlab.lib.pagesizes import A5, landscape
from reportlab.pdfgen.canvas import Canvas

from app.db import DATA
from app.money import fmt_rp

STATE = {"erp_fail": False}


class ErpError(Exception):
    pass


def erp_post(lines: list[dict]) -> str:
    if STATE["erp_fail"]:
        raise ErpError("ERP mock: koneksi ditolak (simulasi)")
    return f"ERP-{datetime.now():%Y%m%d}-{secrets.token_hex(3).upper()}"


def receipt_pdf(receipt_id: int, buyer: str, unit: str, amount: int, date_str: str, lines: list[dict],
                erp_ref: str) -> str:
    path = DATA / "kuitansi" / f"kuitansi-{receipt_id}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(path), pagesize=landscape(A5))
    w, h = landscape(A5)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(36, h - 50, "KUITANSI PENERIMAAN PEMBAYARAN")
    c.setFont("Helvetica", 11)
    y = h - 85
    for label, val in [("No. Kuitansi", f"KW-{receipt_id:06d}"), ("Diterima dari", buyer), ("Unit", unit),
                       ("Tanggal", date_str), ("Jumlah", fmt_rp(amount)), ("Ref. ERP", erp_ref)]:
        c.drawString(36, y, label)
        c.drawString(160, y, f": {val}")
        y -= 20
    y -= 6
    for ln in lines:
        c.drawString(36, y, f"Angsuran ke-{ln['seq']}: pokok {fmt_rp(int(ln['pokok']))}, "
                            f"denda {fmt_rp(int(ln['denda_dibayar']))}")
        y -= 16
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(36, 30, "Kuitansi digital OmniAudit AI (demo). Dokumen ini sah tanpa tanda tangan.")
    c.save()
    return str(path)
