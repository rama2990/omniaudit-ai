import random
from datetime import date
from decimal import Decimal as D

import pytest

from app.calc import ContractTerms, PostedHistory, compute_termin, pph_rate

A = ContractTerms(dpp_kontrak=D(10_000_000_000), um_pct=D("0.10"), target_date=date(2026, 9, 30),
                  pph_rate=pph_rate("PELAKSANAAN", "MENENGAH"))
# 50% sudah diposting: NP 5 M, UM terpotong 500 jt -> saldo 500 jt
A_HIST = PostedHistory(np_sum=D(5_000_000_000), um_sum=D(500_000_000))
B = ContractTerms(dpp_kontrak=D(1_500_000_000), target_date=date(2026, 12, 31),
                  pph_rate=pph_rate("PELAKSANAAN", "KECIL"))
B_HIST = PostedHistory(np_sum=D(600_000_000))


def row(c):
    return [c.np, c.um, c.dpp_faktur, c.ppn, c.bruto, c.ret, c.pen, c.pph, c.net]


def test_contoh_a_klaim():
    c = compute_termin(A, A_HIST, D("0.80"), date(2026, 10, 10))
    assert row(c) == [3_000_000_000, 300_000_000, 2_700_000_000, 297_000_000, 2_997_000_000,
                      150_000_000, 200_000_000, 71_550_000, 2_575_450_000]
    assert c.late_days == 10


def test_contoh_a_terverifikasi():
    c = compute_termin(A, A_HIST, D("0.75"), date(2026, 10, 10))
    assert row(c) == [2_500_000_000, 250_000_000, 2_250_000_000, 247_500_000, 2_497_500_000,
                      125_000_000, 200_000_000, 59_625_000, 2_112_875_000]


def test_contoh_b():
    k = compute_termin(B, B_HIST, D("0.60"), date(2026, 10, 12))
    v = compute_termin(B, B_HIST, D("0.55"), date(2026, 10, 12))
    assert (k.bruto, k.ret, k.pph, k.net) == (333_000_000, 15_000_000, 5_250_000, 312_750_000)
    assert (v.bruto, v.ret, v.pph, v.net) == (249_750_000, 11_250_000, 3_937_500, 234_562_500)
    assert v.pen == 0 and v.um == 0


def test_denda_dibatasi_dan_terbawa():
    c = compute_termin(A, A_HIST, D("0.52"), date(2026, 10, 25))
    assert c.net == 0
    assert c.pen == 185_030_000
    assert c.pen_left == 500_000_000 - 185_030_000


def test_termin_100_ambil_seluruh_saldo_um():
    hist = PostedHistory(np_sum=D(9_000_000_000), um_sum=D(899_999_999))
    c = compute_termin(A, hist, D("1"), date(2026, 9, 1))
    assert c.um == 100_000_001


def test_progres_mundur_tidak_negatif():
    c = compute_termin(A, A_HIST, D("0.40"), date(2026, 9, 1))
    assert c.np == 0 and c.net == 0


def test_properti_jurnal_berimbang_dan_net_tidak_negatif():
    rnd = random.Random(42)
    for _ in range(1000):
        dpp = D(rnd.randint(10**8, 2 * 10**11))
        um_pct = D(rnd.choice([0, 5, 10, 20, 30])) / 100
        prev = D(rnd.randint(0, 99)) / 100
        p = min(D(1), prev + D(rnd.randint(0, 6000)) / 10000)
        np_sum = (dpp * prev).quantize(D(1))
        um_sum = min((um_pct * np_sum).quantize(D(1)), (um_pct * dpp).quantize(D(1)))
        terms = ContractTerms(dpp_kontrak=dpp, um_pct=um_pct, target_date=date(2026, 1, 1),
                              pph_rate=D(rnd.choice(["0.0175", "0.0265", "0.04", "0.035", "0.06"])))
        hist = PostedHistory(np_sum=np_sum, um_sum=um_sum, pen_sum=D(rnd.randint(0, 10**7)))
        c = compute_termin(terms, hist, p, date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + rnd.randint(-30, 90)))
        assert c.np + c.ppn == c.um + c.ret + c.pen + c.pph + c.net
        assert c.net >= 0 and c.dpp_faktur >= 0
        for v in row(c):
            assert v == v.to_integral_value()


@pytest.mark.parametrize("jenis,sbu,rate", [
    ("PELAKSANAAN", "KECIL", "0.0175"), ("PELAKSANAAN", "MENENGAH", "0.0265"),
    ("PELAKSANAAN", "BESAR", "0.0265"), ("PELAKSANAAN", "TANPA", "0.04"),
    ("TERINTEGRASI", "BESAR", "0.0265"), ("TERINTEGRASI", "TANPA", "0.04"),
    ("PERENCANAAN", "KECIL", "0.035"), ("PENGAWASAN", "TANPA", "0.06"),
])
def test_tabel_pph(jenis, sbu, rate):
    assert pph_rate(jenis, sbu) == D(rate)


def test_angka_tidak_bulat_dihitung_manual():
    t = ContractTerms(dpp_kontrak=D(7_345_678_901), pph_rate=D("0.0265"), target_date=date(2027, 1, 1))
    c = compute_termin(t, PostedHistory(np_sum=D(2_754_629_588)), D("0.6125"), date(2026, 10, 1))
    assert (c.np, c.ppn, c.bruto, c.ret, c.pph, c.net) == (
        1_744_598_739, 191_905_861, 1_936_504_600, 87_229_937, 46_231_867, 1_803_042_796)
