"""Adversarial Auditor (PRD FR-15..FR-22) dan siklus status Termin (FR-23). Murni."""
import re
from dataclasses import dataclass
from decimal import Decimal

from app.money import fmt_rp as _rp

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


def pct_id(x: Decimal) -> str:
    """0.8 -> '80%', 0.0175 -> '1,75%'."""
    return f"{x * 100:.2f}".rstrip("0").rstrip(".") + "%"


def norm_invoice(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def norm_npwp(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    return "0" + d if len(d) == 15 else d


def run_rules(c: AuditContext) -> list[Anomaly]:
    out: list[Anomaly] = []
    add = lambda code, sev, msg: out.append(Anomaly(code, sev, msg))  # noqa: E731
    if not c.contract_found:
        add("KONTRAK_TIDAK_DITEMUKAN", "HIGH", "Contract not found in this SPV. Link the contract manually.")
    if c.duplicate == "OTHER_SPV":
        add("KLAIM_GANDA", "CRITICAL", "The same invoice number and tax ID exist in another SPV (possible double billing).")
    elif c.duplicate == "SAME_SPV":
        add("KLAIM_GANDA", "HIGH", "The same invoice number and tax ID were already submitted in this SPV.")
    k, b = c.progres_klaim, c.progres_bap
    if k is not None and b is not None and k > b:
        add("OVERBILLING", "HIGH", f"Claimed progress {pct_id(k)} exceeds inspected progress {pct_id(b)}. Recalculated using inspected progress.")
    if c.retensi_tertulis is None or c.retensi_tertulis == 0:
        add("OMISI_RETENSI", "MEDIUM", "The invoice does not state retention. Retention is still deducted per the contract.")
    if c.line_items_sum is not None and c.ppn_tertulis is not None and c.bruto_tertulis is not None \
            and abs(c.line_items_sum + c.ppn_tertulis - c.bruto_tertulis) > 1:
        add("MATEMATIKA", "HIGH", f"Line items plus VAT ({_rp(c.line_items_sum + c.ppn_tertulis)}) "
                                  f"do not equal the stated gross amount ({_rp(c.bruto_tertulis)}).")
    if c.bruto_tertulis is not None and c.bruto_klaim_calc is not None \
            and abs(c.bruto_tertulis - c.bruto_klaim_calc) > 1000:
        add("NILAI_TIDAK_SESUAI_PROGRES", "HIGH", f"Stated gross amount {_rp(c.bruto_tertulis)} does not match the value of "
                                                  f"the claimed progress ({_rp(c.bruto_klaim_calc)}).")
    if c.pph_tertulis_rate is not None and c.pph_master is not None and c.pph_tertulis_rate != c.pph_master:
        add("PAJAK_SBU", "MEDIUM", f"Withholding tax rate on the invoice ({pct_id(c.pph_tertulis_rate)}) does not match the vendor grade "
                                   f"({pct_id(c.pph_master)}). The master rate is used.")
    if not c.faktur_found:
        add("FAKTUR_PAJAK", "MEDIUM", "No tax invoice found. Input VAT cannot be credited yet.")
    else:
        if c.faktur_ppn is not None and c.ppn_klaim_calc is not None and abs(c.faktur_ppn - c.ppn_klaim_calc) > 1:
            add("FAKTUR_PAJAK", "MEDIUM", "VAT on the tax invoice differs from the calculated VAT. Input VAT cannot be credited yet.")
        if c.faktur_npwp and c.vendor_npwp and norm_npwp(c.faktur_npwp) != norm_npwp(c.vendor_npwp):
            add("FAKTUR_PAJAK", "MEDIUM", "The seller tax ID on the tax invoice differs from the vendor tax ID.")
    if k is not None and k <= c.progres_prev:
        add("TERMIN_TIDAK_VALID", "HIGH", "Claimed progress is not above previous progress (possibly incremental progress).")
    if (k is not None and k > 1) or (b is not None and b > 1):
        add("TERMIN_TIDAK_VALID", "HIGH", "Progress exceeds 100%.")
    if c.other_open_termin:
        add("TERMIN_TIDAK_VALID", "HIGH", "A previous bill on this contract has not been posted yet.")
    if c.pen_left_at_full:
        add("TERMIN_TIDAK_VALID", "HIGH", "Progress is 100% but an outstanding late penalty has not been deducted.")
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
        raise InvalidTransition(f"Action {action} is not allowed in status {status}")
    roles, target = rule
    if role not in roles:
        raise Forbidden(f"Role {role} may not perform {action}")
    return target
