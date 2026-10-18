from dataclasses import replace
from decimal import Decimal as D

import pytest

from app.audit import (AP, CFO, AuditContext, Forbidden, InvalidTransition, decide_status, needs_cfo,
                       norm_invoice, norm_npwp, run_rules, transition)

CLEAN = AuditContext(
    contract_found=True, progres_klaim=D("0.60"), progres_bap=D("0.60"), progres_prev=D("0.40"),
    retensi_tertulis=D(15_000_000), pph_tertulis_rate=D("0.0175"), pph_master=D("0.0175"),
    bruto_tertulis=D(333_000_000), bruto_klaim_calc=D(333_000_000),
    line_items_sum=D(300_000_000), ppn_tertulis=D(33_000_000),
    faktur_found=True, faktur_ppn=D(33_000_000), faktur_npwp="0123456789012345",
    vendor_npwp="0123456789012345", ppn_klaim_calc=D(33_000_000),
)


def codes(ctx):
    return {(a.code, a.severity) for a in run_rules(ctx)}


def test_bersih_tanpa_anomali():
    assert run_rules(CLEAN) == []


@pytest.mark.parametrize("change,expected", [
    (dict(progres_bap=D("0.55")), ("OVERBILLING", "HIGH")),
    (dict(duplicate="OTHER_SPV"), ("KLAIM_GANDA", "CRITICAL")),
    (dict(duplicate="SAME_SPV"), ("KLAIM_GANDA", "HIGH")),
    (dict(retensi_tertulis=None), ("OMISI_RETENSI", "MEDIUM")),
    (dict(retensi_tertulis=D(0)), ("OMISI_RETENSI", "MEDIUM")),
    (dict(line_items_sum=D(290_000_000)), ("MATEMATIKA", "HIGH")),
    (dict(bruto_tertulis=D(350_000_000), line_items_sum=D(317_000_000)), ("NILAI_TIDAK_SESUAI_PROGRES", "HIGH")),
    (dict(pph_tertulis_rate=D("0.0265")), ("PAJAK_SBU", "MEDIUM")),
    (dict(faktur_found=False), ("FAKTUR_PAJAK", "MEDIUM")),
    (dict(faktur_ppn=D(30_000_000)), ("FAKTUR_PAJAK", "MEDIUM")),
    (dict(faktur_npwp="0999999999999999"), ("FAKTUR_PAJAK", "MEDIUM")),
    (dict(progres_klaim=D("0.40"), progres_bap=D("0.40")), ("TERMIN_TIDAK_VALID", "HIGH")),
    (dict(progres_klaim=D("1.10"), progres_bap=D("1.10")), ("TERMIN_TIDAK_VALID", "HIGH")),
    (dict(other_open_termin=True), ("TERMIN_TIDAK_VALID", "HIGH")),
    (dict(pen_left_at_full=True), ("TERMIN_TIDAK_VALID", "HIGH")),
    (dict(contract_found=False), ("KONTRAK_TIDAK_DITEMUKAN", "HIGH")),
])
def test_setiap_anomali(change, expected):
    assert expected in codes(replace(CLEAN, **change))


def test_pph_tidak_tercantum_tidak_memicu():
    assert codes(replace(CLEAN, pph_tertulis_rate=None)) == set()


def test_prioritas_status():
    hi = run_rules(replace(CLEAN, progres_bap=D("0.55")))
    crit = run_rules(replace(CLEAN, progres_bap=D("0.55"), duplicate="OTHER_SPV"))
    med = run_rules(replace(CLEAN, retensi_tertulis=None))
    assert decide_status(crit, D("0.99")) == "HARD_STOP"
    assert decide_status(hi, D("0.99")) == "DISPUTE"
    assert decide_status(med, D("0.99")) == "READY"
    assert decide_status([], D("0.84")) == "DISPUTE"
    assert decide_status([], D("0.85")) == "READY"


def test_needs_cfo_pakai_nilai_terbesar():
    assert needs_cfo(D(400_000_000), D(500_000_001))
    assert needs_cfo(D(500_000_001), None)
    assert not needs_cfo(D(500_000_000), D(333_000_000))


def test_transisi():
    assert transition("READY", "post", AP) == "POST"
    assert transition("HARD_STOP", "cfo_unlock", CFO) == "DISPUTE"
    with pytest.raises(Forbidden):
        transition("HARD_STOP", "cfo_unlock", AP)
    with pytest.raises(Forbidden):
        transition("HARD_STOP", "reject", AP)
    with pytest.raises(InvalidTransition):
        transition("POSTED", "post", AP)
    assert transition("DISPUTE", "submit_cfo", AP) == "MENUNGGU_CFO"
    assert transition("MENUNGGU_CFO", "cfo_approve", CFO) == "POST"


def test_normalisasi():
    assert norm_invoice(" inv/2026-001 ") == "INV2026001"
    assert norm_npwp("01.234.567.8-901.234") == "0012345678901234"
    assert norm_npwp("0123456789012345") == "0123456789012345"
