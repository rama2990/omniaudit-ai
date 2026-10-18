"""Reconciliation Agent: Match Score Penerimaan vs Unit (PRD FR-31). Murni."""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import jellyfish

from app.allocation import TOLERANSI, Inst, denda

W_UNIT, W_NAMA, W_NOMINAL = Decimal("0.45"), Decimal("0.35"), Decimal("0.20")
RECOMMEND_MIN, LEAD_MIN = Decimal("0.85"), Decimal("0.10")
UNIT_WORDS = {"BLOK", "BLK", "TOWER", "TWR", "UNIT", "NO"}
TITLES = {"BPK", "BAPAK", "IBU", "SDR", "SDRI", "H", "HJ", "TN", "NY", "MR", "MRS"}
NOISE = {"TRF", "TRANSFER", "ANGS", "ANGSURAN", "CICILAN", "BAYAR", "PEMBAYARAN", "DP", "KE", "UTK", "UNTUK",
         "VA", "BCA", "BNI", "BRI", "MANDIRI", "KPR", "BULAN", "PELUNASAN"}


@dataclass(frozen=True)
class Receipt:
    date: date
    sender: str
    amount: Decimal
    memo: str
    va: str | None = None


@dataclass(frozen=True)
class UnitInfo:
    id: int
    code: str
    buyer: str
    va: str | None
    installments: list[Inst]


@dataclass(frozen=True)
class Candidate:
    unit_id: int
    code: str
    buyer: str
    s_unit: Decimal
    s_nama: Decimal
    s_nominal: Decimal
    score: Decimal


def tokens(s: str) -> list[str]:
    out = []
    for t in re.findall(r"[A-Z]+|\d+", (s or "").upper()):
        if t in UNIT_WORDS:
            continue
        out.append(str(int(t)) if t.isdigit() else t)
    return out


def norm_unit(s: str) -> str:
    return "-".join(tokens(s))


def _jw(a: str, b: str) -> Decimal:
    return Decimal(str(round(jellyfish.jaro_winkler_similarity(a, b), 4))) if a and b else Decimal(0)


def s_unit(memo_tokens: list[str], unit_norm: str) -> Decimal:
    ut = unit_norm.split("-")
    best = Decimal(0)
    for i in range(len(memo_tokens) - len(ut) + 1):
        w = memo_tokens[i:i + len(ut)]
        if w == ut:
            return Decimal(1)
        # angka harus sama persis; huruf boleh mirip
        if all((u == x) if u.isdigit() else (not x.isdigit() and _jw(u, x) >= Decimal("0.80")) for u, x in zip(ut, w)):
            best = Decimal("0.7")
    return best


def _name(s: str) -> str:
    return " ".join(t for t in re.findall(r"[A-Z]+", (s or "").upper())
                    if t not in TITLES | NOISE | UNIT_WORDS and len(t) > 1)


def s_nama(sender: str, memo: str, buyer: str) -> Decimal:
    b = _name(buyer)
    return max(_jw(_name(sender), b), _jw(_name(memo), b))


def _nominal_score(amount: Decimal, target: Decimal) -> Decimal:
    diff = abs(amount - target)
    if diff <= TOLERANSI:
        return Decimal(1)
    return max(Decimal(0), 1 - (diff - TOLERANSI) / target)


def s_nominal(amount: Decimal, unpaid: list[Inst], pay_date: date) -> Decimal:
    best, plain, with_pen = Decimal(0), Decimal(0), Decimal(0)
    for i in sorted(unpaid, key=lambda x: x.due)[:6]:
        plain += i.remaining
        with_pen += i.remaining + denda(i.remaining, i.due, pay_date)
        best = max(best, _nominal_score(amount, plain), _nominal_score(amount, with_pen))
    return best


def score_receipt(r: Receipt, units: list[UnitInfo]) -> list[Candidate]:
    mt = tokens(r.memo)
    cands = []
    for u in units:
        unpaid = [i for i in u.installments if i.remaining > 0]
        if not unpaid:
            continue
        su, sn, sv = s_unit(mt, norm_unit(u.code)), s_nama(r.sender, r.memo, u.buyer), s_nominal(r.amount, unpaid, r.date)
        score = (W_UNIT * su + W_NAMA * sn + W_NOMINAL * sv).quantize(Decimal("0.0001"))
        cands.append(Candidate(u.id, u.code, u.buyer, su, sn, sv.quantize(Decimal("0.0001")), score))
    cands.sort(key=lambda c: c.score, reverse=True)
    return cands[:3]


def match_status(cands: list[Candidate]) -> str:
    if not cands or cands[0].score < RECOMMEND_MIN:
        return "MANUAL_REVIEW"
    if len(cands) > 1 and cands[0].score - cands[1].score < LEAD_MIN:
        return "MANUAL_REVIEW"
    return "RECOMMENDED"
