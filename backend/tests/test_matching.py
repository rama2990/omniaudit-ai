from datetime import date
from decimal import Decimal as D

from app.allocation import Inst, allocate, denda
from app.journal import Unbalanced, ap_journal, ar_journal, check_balanced
from app.matching import Receipt, UnitInfo, match_status, norm_unit, s_nama, s_nominal, s_unit, score_receipt, tokens


def inst(i, due, amount, paid=0):
    return Inst(id=i, seq=i, due=due, amount=D(amount), paid=D(paid))


def test_norm_unit():
    assert norm_unit("BLOK C1/02") == norm_unit("C1-02") == norm_unit("c1-2") == "C-1-2"
    assert norm_unit("TOWER A-12-04") == "A-12-4"


def test_s_unit():
    memo = tokens("TRF BPK SUTRISNO BLK C1/02")
    assert s_unit(memo, norm_unit("C1-02")) == 1
    assert s_unit(memo, norm_unit("C1-03")) == 0
    assert s_unit(tokens("BAYAR TWR AA 12 04"), norm_unit("A-12-04")) == D("0.7")
    assert s_unit(tokens("TRANSFER ANGSURAN"), norm_unit("C1-02")) == 0


def test_s_nama_buang_gelar():
    assert s_nama("BPK SUTRISNO", "TRF BPK SUTRISNO BLK C1/02", "Sutrisno Wibowo") > D("0.9")
    assert s_nama("PT LAIN", "", "Sutrisno Wibowo") < D("0.6")


def test_s_nominal():
    unpaid = [inst(1, date(2026, 9, 1), 5_000_000), inst(2, date(2026, 10, 1), 5_000_000)]
    pay_date = date(2026, 9, 1)
    assert s_nominal(D(5_000_000), unpaid, pay_date) == 1
    assert s_nominal(D(4_800_000), unpaid, pay_date) == 1  # selisih <= 250rb
    assert s_nominal(D(10_000_000), unpaid, pay_date) == 1  # 2 angsuran sekaligus
    assert s_nominal(D(2_500_000), unpaid, pay_date) == D("0.55")


def test_score_dan_status():
    units = [
        UnitInfo(1, "C1-02", "Sutrisno Wibowo", None, [inst(1, date(2026, 9, 1), 5_000_000)]),
        UnitInfo(2, "C1-03", "Sutrisno Wibowo", None, [inst(2, date(2026, 9, 1), 5_000_000)]),
        UnitInfo(3, "D2-01", "Ani Lestari", None, [inst(3, date(2026, 9, 1), 7_000_000)]),
    ]
    r = Receipt(date(2026, 9, 13), "BPK SUTRISNO", D(5_000_000), "TRF BPK SUTRISNO BLK C1/02")
    cands = score_receipt(r, units)
    assert cands[0].unit_id == 1 and cands[0].score >= D("0.85")
    assert match_status(cands) == "RECOMMENDED"
    # dua kandidat sama kuat -> manual
    r2 = Receipt(date(2026, 9, 13), "BPK SUTRISNO", D(5_000_000), "TRF ANGSURAN")
    assert match_status(score_receipt(r2, units)) == "MANUAL_REVIEW"


def test_denda_angsuran_tanpa_batas():
    assert denda(D(5_000_000), date(2026, 9, 1), date(2026, 9, 13)) == 60_000
    assert denda(D(5_000_000), date(2026, 9, 1), date(2028, 9, 1)) == 3_655_000
    assert denda(D(5_000_000), date(2026, 9, 1), date(2026, 8, 30)) == 0


def test_alokasi_fifo_denda_titipan():
    unpaid = [inst(1, date(2026, 8, 1), 5_000_000), inst(2, date(2026, 9, 1), 5_000_000)]
    a = allocate(D(11_000_000), date(2026, 9, 11), unpaid, waive=False)
    l1, l2 = a.lines
    assert (l1.pokok, l1.late_days, l1.denda, l1.denda_dibayar) == (5_000_000, 41, 205_000, 205_000)
    assert (l2.pokok, l2.late_days, l2.denda, l2.denda_dibayar) == (5_000_000, 10, 50_000, 50_000)
    assert a.titipan == 11_000_000 - 10_255_000
    assert all(x.settled for x in a.lines)


def test_alokasi_waiver_dan_kurang_bayar():
    unpaid = [inst(1, date(2026, 9, 1), 5_000_000)]
    a = allocate(D(4_850_000), date(2026, 9, 13), unpaid, waive=True)
    l1 = a.lines[0]
    assert l1.settled and a.selisih_transfer == 150_000
    assert l1.denda == 58_200 and l1.denda_dibayar == 0 and a.waived
    j = ar_journal(a, D(4_850_000))
    check_balanced(j)
    assert not any("Denda" in x.account for x in j)


def test_alokasi_bayar_sebagian_tidak_lunas():
    a = allocate(D(3_000_000), date(2026, 9, 1), [inst(1, date(2026, 9, 1), 5_000_000)], waive=False)
    assert a.lines[0].pokok == 3_000_000 and not a.lines[0].settled


def test_jurnal_ar_berimbang_dengan_denda():
    unpaid = [inst(1, date(2026, 8, 1), 5_000_000)]
    a = allocate(D(5_100_000), date(2026, 9, 11), unpaid, waive=False)
    j = ar_journal(a, D(5_100_000))
    check_balanced(j)
    accounts = {x.account for x in j}
    assert "Pendapatan Denda Angsuran" in accounts and "Piutang Denda Angsuran" in accounts


def test_jurnal_ap_contoh_a():
    from app.calc import ContractTerms, PostedHistory, compute_termin
    t = ContractTerms(dpp_kontrak=D(10**10), um_pct=D("0.1"), target_date=date(2026, 9, 30), pph_rate=D("0.0265"))
    c = compute_termin(t, PostedHistory(D(5 * 10**9), D(5 * 10**8)), D("0.75"), date(2026, 10, 10))
    j = ap_journal(c)
    assert sum(x.amount for x in j if x.side == "D") == 2_747_500_000
    assert [x.amount for x in j if x.account == "Utang Usaha"] == [2_112_875_000]


def test_unbalanced_raises():
    from app.journal import JournalLine
    try:
        check_balanced([JournalLine("D", "Bank", D(1)), JournalLine("C", "X", D(2))])
    except Unbalanced:
        return
    raise AssertionError("should raise")
