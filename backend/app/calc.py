"""Mesin kalkulasi Termin AP (PRD FR-8..FR-14). Murni: tanpa DB, tanpa jaringan."""
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal

from app.money import ZERO, rp

D = Decimal
PPN_RATE = D("0.11")  # 12% x 11/12

_PPH = {
    "PELAKSANAAN": {"KECIL": "0.0175", "MENENGAH": "0.0265", "BESAR": "0.0265", "TANPA": "0.04"},
    "TERINTEGRASI": {"KECIL": "0.0265", "MENENGAH": "0.0265", "BESAR": "0.0265", "TANPA": "0.04"},
    "PERENCANAAN": {"KECIL": "0.035", "MENENGAH": "0.035", "BESAR": "0.035", "TANPA": "0.06"},
    "PENGAWASAN": {"KECIL": "0.035", "MENENGAH": "0.035", "BESAR": "0.035", "TANPA": "0.06"},
}


def pph_rate(jenis: str, sbu: str) -> Decimal:
    return D(_PPH[jenis][sbu])


@dataclass(frozen=True)
class ContractTerms:
    dpp_kontrak: Decimal
    pph_rate: Decimal
    target_date: date | None = None
    ret_pct: Decimal = D("0.05")
    um_pct: Decimal = ZERO
    denda_harian: Decimal = D("0.002")
    denda_cap: Decimal = D("0.05")


@dataclass(frozen=True)
class PostedHistory:
    """Jumlah dari Termin yang sudah POSTED pada Kontrak ini."""
    np_sum: Decimal = ZERO
    um_sum: Decimal = ZERO
    pen_sum: Decimal = ZERO


@dataclass(frozen=True)
class TerminCalc:
    p: Decimal
    np: Decimal
    um: Decimal
    dpp_faktur: Decimal
    ppn: Decimal
    bruto: Decimal
    ret: Decimal
    pen: Decimal
    pph: Decimal
    net: Decimal
    late_days: int
    pen_left: Decimal  # Denda Tertunggak yang terbawa ke Termin berikutnya
    um_saldo_before: Decimal

    def as_dict(self) -> dict:
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in asdict(self).items()}


def compute_termin(t: ContractTerms, h: PostedHistory, p: Decimal, bap_date: date,
                   ppn_rate: Decimal = PPN_RATE) -> TerminCalc:
    np_ = max(ZERO, rp(t.dpp_kontrak * p) - h.np_sum)  # mundur/tanpa progres -> ditangkap audit FR-22
    um_saldo = max(ZERO, rp(t.um_pct * t.dpp_kontrak) - h.um_sum)
    um = um_saldo if p >= 1 else min(rp(t.um_pct * np_), um_saldo)
    um = min(um, np_)
    dpp_f = np_ - um
    ppn = rp(dpp_f * ppn_rate)
    bruto = dpp_f + ppn
    pph = rp(dpp_f * t.pph_rate)
    # ponytail: retensi dibatasi agar Net >= 0 bila termin habis untuk UM (hanya terjadi di termin akhir)
    ret = min(rp(t.ret_pct * np_), max(ZERO, bruto - pph))
    late = max(0, (bap_date - t.target_date).days) if t.target_date else 0
    pen_cum = min(rp(t.dpp_kontrak * t.denda_harian * late), rp(t.dpp_kontrak * t.denda_cap))
    outstanding = max(ZERO, pen_cum - h.pen_sum)
    pen = min(outstanding, max(ZERO, bruto - ret - pph))
    net = bruto - ret - pen - pph
    return TerminCalc(p=p, np=np_, um=um, dpp_faktur=dpp_f, ppn=ppn, bruto=bruto, ret=ret, pen=pen,
                      pph=pph, net=net, late_days=late, pen_left=outstanding - pen, um_saldo_before=um_saldo)
