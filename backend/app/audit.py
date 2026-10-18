"""Adversarial Auditor (PRD FR-15..FR-22) dan siklus status Termin (FR-23). Murni."""
import re
from dataclasses import dataclass
from decimal import Decimal

AP, AR, CFO = "ROLE_FIN_AP", "ROLE_SALES_AR", "ROLE_CFO_EXEC"
CFO_THRESHOLD = Decimal(500_000_000)
CONFIDENCE_MIN = Decimal("0.85")


@dataclass(frozen=True)
class Anomaly:
    code: str
    severity: str  # MEDIUM | HIGH | CRITICAL
    message: str


@dataclass(frozen=True)
class AuditContext:
    contract_found: bool
    progres_klaim: Decimal | None
    progres_bap: Decimal | None
    progres_prev: Decimal
    pph_master: Decimal | None
    bruto_tertulis: Decimal | None
    bruto_klaim_calc: Decimal | None
    vendor_npwp: str | None
    ppn_klaim_calc: Decimal | None
    retensi_tertulis: Decimal | None = None
    pph_tertulis_rate: Decimal | None = None
    line_items_sum: Decimal | None = None
    ppn_tertulis: Decimal | None = None
    faktur_found: bool = False
    faktur_ppn: Decimal | None = None
    faktur_npwp: str | None = None
    duplicate: str | None = None  # None | SAME_SPV | OTHER_SPV
    other_open_termin: bool = False
    pen_left_at_full: bool = False


def norm_invoice(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def norm_npwp(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    return "0" + d if len(d) == 15 else d


def run_rules(c: AuditContext) -> list[Anomaly]:
    out: list[Anomaly] = []
    add = lambda code, sev, msg: out.append(Anomaly(code, sev, msg))  # noqa: E731
    if not c.contract_found:
        add("KONTRAK_TIDAK_DITEMUKAN", "HIGH", "Kontrak tidak ditemukan di SPV ini. Pilih Kontrak secara manual.")
    if c.duplicate == "OTHER_SPV":
        add("KLAIM_GANDA", "CRITICAL", "Nomor invoice + NPWP yang sama ditemukan di SPV lain (indikasi double-billing).")
    elif c.duplicate == "SAME_SPV":
        add("KLAIM_GANDA", "HIGH", "Nomor invoice + NPWP yang sama sudah pernah diajukan di SPV ini.")
    k, b = c.progres_klaim, c.progres_bap
    if k is not None and b is not None and k > b:
        add("OVERBILLING", "HIGH", f"Progres Klaim {k:.2%} melebihi Progres BAP {b:.2%}. Dihitung ulang memakai Progres BAP.")
    if c.retensi_tertulis is None or c.retensi_tertulis == 0:
        add("OMISI_RETENSI", "MEDIUM", "Invoice tidak mencantumkan Retensi. Retensi tetap dipotong sesuai Kontrak.")
    if c.line_items_sum is not None and c.ppn_tertulis is not None and c.bruto_tertulis is not None \
            and abs(c.line_items_sum + c.ppn_tertulis - c.bruto_tertulis) > 1:
        add("MATEMATIKA", "HIGH", f"Jumlah line item + PPN ({c.line_items_sum + c.ppn_tertulis:,.0f}) "
                                  f"tidak sama dengan Bruto Tertulis ({c.bruto_tertulis:,.0f}).")
    if c.bruto_tertulis is not None and c.bruto_klaim_calc is not None \
            and abs(c.bruto_tertulis - c.bruto_klaim_calc) > 1000:
        add("NILAI_TIDAK_SESUAI_PROGRES", "HIGH", f"Bruto Tertulis {c.bruto_tertulis:,.0f} tidak sesuai nilai "
                                                  f"Progres Klaim ({c.bruto_klaim_calc:,.0f}).")
    if c.pph_tertulis_rate is not None and c.pph_master is not None and c.pph_tertulis_rate != c.pph_master:
        add("PAJAK_SBU", "MEDIUM", f"Tarif PPh di invoice {c.pph_tertulis_rate:.2%} tidak sesuai SBU Vendor "
                                   f"({c.pph_master:.2%}). Dipakai tarif master.")
    if not c.faktur_found:
        add("FAKTUR_PAJAK", "MEDIUM", "Faktur Pajak tidak ditemukan. PPN Masukan belum dapat dikreditkan.")
    else:
        if c.faktur_ppn is not None and c.ppn_klaim_calc is not None and abs(c.faktur_ppn - c.ppn_klaim_calc) > 1:
            add("FAKTUR_PAJAK", "MEDIUM", "PPN di Faktur Pajak tidak sama dengan PPN hitungan. PPN Masukan belum dapat dikreditkan.")
        if c.faktur_npwp and c.vendor_npwp and norm_npwp(c.faktur_npwp) != norm_npwp(c.vendor_npwp):
            add("FAKTUR_PAJAK", "MEDIUM", "NPWP penjual di Faktur Pajak berbeda dari NPWP Vendor.")
    if k is not None and k <= c.progres_prev:
        add("TERMIN_TIDAK_VALID", "HIGH", "Progres Klaim tidak melebihi Progres Sebelumnya (kemungkinan progres inkremental).")
    if (k is not None and k > 1) or (b is not None and b > 1):
        add("TERMIN_TIDAK_VALID", "HIGH", "Progres melebihi 100%.")
    if c.other_open_termin:
        add("TERMIN_TIDAK_VALID", "HIGH", "Termin sebelumnya pada Kontrak ini belum diposting.")
    if c.pen_left_at_full:
        add("TERMIN_TIDAK_VALID", "HIGH", "Progres 100% tetapi masih ada Denda Tertunggak yang belum terpotong.")
    return out


def decide_status(anoms: list[Anomaly], confidence: Decimal) -> str:
    sev = {a.severity for a in anoms}
    if "CRITICAL" in sev:
        return "HARD_STOP"
    if "HIGH" in sev or confidence < CONFIDENCE_MIN:
        return "DISPUTE"
    return "READY"


def needs_cfo(bruto_tertulis: Decimal | None, bruto_klaim: Decimal | None) -> bool:
    return max(bruto_tertulis or 0, bruto_klaim or 0) > CFO_THRESHOLD


class Forbidden(Exception):
    pass


class InvalidTransition(Exception):
    pass


# (status, aksi) -> (peran yang boleh, status tujuan). "POST" = jalankan posting ERP.
ALLOWED = {
    ("READY", "post"): ({AP}, "POST"),
    ("DISPUTE", "post"): ({AP}, "POST"),  # API menolak bila needs_cfo
    ("DISPUTE", "submit_cfo"): ({AP}, "MENUNGGU_CFO"),
    ("READY", "flag"): ({AP}, "DISPUTE"),
    ("READY", "reject"): ({AP}, "REJECTED"),
    ("DISPUTE", "reject"): ({AP}, "REJECTED"),
    ("MENUNGGU_CFO", "cfo_approve"): ({CFO}, "POST"),
    ("MENUNGGU_CFO", "cfo_reject"): ({CFO}, "REJECTED"),
    ("HARD_STOP", "cfo_unlock"): ({CFO}, "DISPUTE"),
    ("HARD_STOP", "cfo_reject"): ({CFO}, "REJECTED"),
    ("HARD_STOP", "reject"): ({CFO}, "REJECTED"),
    ("ERP_GAGAL", "resend"): ({AP, CFO}, "POST"),
    ("GAGAL_PROSES", "retry"): ({AP}, "PROCESSING"),
}


def transition(status: str, action: str, role: str) -> str:
    rule = ALLOWED.get((status, action))
    if rule is None:
        raise InvalidTransition(f"Aksi {action} tidak berlaku untuk status {status}")
    roles, target = rule
    if role not in roles:
        raise Forbidden(f"Peran {role} tidak boleh melakukan {action}")
    return target
