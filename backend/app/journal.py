"""Penyusun Batch Jurnal AP & AR (FR-27, FR-36). Murni; batch tidak berimbang = error."""
from dataclasses import dataclass
from decimal import Decimal

from app.allocation import Allocation
from app.calc import TerminCalc


@dataclass(frozen=True)
class JournalLine:
    side: str  # D | C
    account: str
    amount: Decimal


class Unbalanced(Exception):
    pass


def check_balanced(lines: list[JournalLine]) -> list[JournalLine]:
    d = sum(l.amount for l in lines if l.side == "D")
    c = sum(l.amount for l in lines if l.side == "C")
    if d != c:
        raise Unbalanced(f"Debit {d} != Kredit {c}")
    return lines


def _nz(lines):
    return [l for l in lines if l.amount]


def ap_journal(c: TerminCalc) -> list[JournalLine]:
    return check_balanced(_nz([
        JournalLine("D", "Aset Real Estat – Bangunan dalam Penyelesaian", c.np),
        JournalLine("D", "PPN Masukan", c.ppn),
        JournalLine("C", "Uang Muka Kontraktor", c.um),
        JournalLine("C", "Utang Retensi", c.ret),
        JournalLine("C", "Pendapatan Lain-lain – Denda Kontraktor", c.pen),
        JournalLine("C", "Utang PPh 4(2)", c.pph),
        JournalLine("C", "Utang Usaha", c.net),
    ]))


def ar_journal(a: Allocation, amount: Decimal, include_penalty: bool | None = None) -> list[JournalLine]:
    """include_penalty=False menahan jurnal denda (Waiver menunggu CFO)."""
    pen = Decimal(0) if (a.waived if include_penalty is None else not include_penalty) else a.total_denda
    pokok = sum(l.pokok for l in a.lines)
    return check_balanced(_nz([
        JournalLine("D", "Bank", amount),
        JournalLine("D", "Beban Selisih Biaya Transfer", a.selisih_transfer),
        JournalLine("D", "Piutang Denda Angsuran", pen),
        JournalLine("C", "Pendapatan Denda Angsuran", pen),
        JournalLine("C", "Piutang Angsuran", pokok + a.selisih_transfer),
        JournalLine("C", "Piutang Denda Angsuran", sum(l.denda_dibayar for l in a.lines)),
        JournalLine("C", "Titipan Pembeli", a.titipan),
    ]))


def penalty_journal(amount: Decimal) -> list[JournalLine]:
    """Dipakai saat CFO menolak Waiver: denda yang ditahan dibukukan."""
    return check_balanced(_nz([JournalLine("D", "Piutang Denda Angsuran", amount),
                               JournalLine("C", "Pendapatan Denda Angsuran", amount)]))
