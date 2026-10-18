"""Denda Angsuran (FR-34) dan alokasi Penerimaan FIFO (FR-36). Murni."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.money import ZERO, rp

DENDA_PER_HARI = Decimal("0.001")
TOLERANSI = Decimal(250_000)


@dataclass(frozen=True)
class Inst:
    id: int
    seq: int
    due: date
    amount: Decimal
    paid: Decimal = ZERO

    @property
    def remaining(self) -> Decimal:
        return self.amount - self.paid


@dataclass(frozen=True)
class Line:
    inst_id: int
    seq: int
    due: date
    pokok: Decimal
    late_days: int
    denda: Decimal
    denda_dibayar: Decimal
    settled: bool


@dataclass
class Allocation:
    lines: list[Line] = field(default_factory=list)
    titipan: Decimal = ZERO
    selisih_transfer: Decimal = ZERO
    waived: bool = False

    @property
    def total_denda(self) -> Decimal:
        return sum((l.denda for l in self.lines), ZERO)


def denda(pokok: Decimal, due: date, pay_date: date) -> Decimal:
    """Tanpa batas atas (keputusan user)."""
    return rp(pokok * DENDA_PER_HARI * max(0, (pay_date - due).days))


def allocate(amount: Decimal, pay_date: date, unpaid: list[Inst], waive: bool) -> Allocation:
    """Urutan: pokok angsuran tertua -> dendanya -> angsuran berikutnya -> Titipan."""
    a = Allocation(waived=waive)
    left = amount
    for i in sorted(unpaid, key=lambda x: x.due):
        if left <= 0:
            break
        pay = min(left, i.remaining)
        left -= pay
        gap = i.remaining - pay
        settled = gap == 0 or (left == 0 and gap <= TOLERANSI)  # kurang bayar <= Rp250rb dianggap lunas
        if gap and settled:
            a.selisih_transfer += gap
        late = max(0, (pay_date - i.due).days)
        d = denda(pay, i.due, pay_date)
        d_paid = ZERO if waive else min(left, d)
        left -= d_paid
        a.lines.append(Line(i.id, i.seq, i.due, pay, late, d, d_paid, settled))
    a.titipan = left
    return a
