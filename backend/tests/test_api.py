import csv
import io

import pytest
from fastapi.testclient import TestClient

from app import seed as seedmod


@pytest.fixture(scope="module")
def c():
    seedmod.seed(fast=True)
    from app.main import app
    with TestClient(app) as client:
        yield client


def H(p):
    return {"X-Persona": p}


def upload(c, name, spv, who="dewi"):
    with open(seedmod.DEMO / name, "rb") as f:
        r = c.post("/api/ap/upload", data={"spv": spv}, files={"file": (name, f, "application/pdf")}, headers=H(who))
    assert r.status_code == 200, r.text
    return c.get(f"/api/ap/termin/{r.json()['id']}", headers=H(who)).json()


def act(c, tid, who, action, **kw):
    return c.post(f"/api/ap/termin/{tid}/action", json={"action": action, **kw}, headers=H(who))


def codes(t):
    return {(a["code"], a["severity"]) for a in t["anomalies"]}


def test_isolasi_spv(c):
    assert c.get("/api/dashboard?spv=GCT3", headers=H("dewi")).status_code == 403
    assert c.get("/api/dashboard?spv=ALL", headers=H("dewi")).status_code == 403
    assert c.get("/api/dashboard?spv=ALL", headers=H("hartono")).status_code == 200
    t = upload(c, "03_kontrak_D_bersih_scan.pdf", "GCT3", who="budi")
    assert c.get(f"/api/ap/termin/{t['id']}", headers=H("dewi")).status_code == 403
    assert c.post("/api/ap/upload", data={"spv": "SLO1"}, files={"file": ("x.pdf", b"%PDF", "application/pdf")},
                  headers=H("andi")).status_code == 403


def test_uj1_overbilling_post_langsung(c):
    t = upload(c, "01_UJ1_kontrak_B_overbilling.pdf", "SLO1")
    assert t["status"] == "DISPUTE" and not t["needs_cfo"]
    assert codes(t) == {("OVERBILLING", "HIGH")}
    assert t["calc_claim"]["net"] == "312750000" and t["calc_verified"]["net"] == "234562500"
    assert "post" in t["actions"] and "submit_cfo" not in t["actions"]
    assert any(f["boxes"] for f in t["fields"] if f["name"] == "progres_bap")
    t = act(c, t["id"], "dewi", "post").json()
    assert t["status"] == "POSTED" and t["erp_ref"].startswith("ERP-")
    assert sum(l["amount"] for l in t["journal"] if l["side"] == "D") == 249_750_000


def test_uj3_cfo(c):
    t = upload(c, "02_UJ3_kontrak_A_butuh_CFO.pdf", "SLO1")
    assert t["status"] == "DISPUTE" and t["needs_cfo"]
    assert t["calc_verified"]["net"] == "2112875000" and t["calc_claim"]["bruto"] == "2997000000"
    assert act(c, t["id"], "dewi", "post").status_code == 409
    assert act(c, t["id"], "dewi", "submit_cfo").json()["status"] == "MENUNGGU_CFO"
    assert act(c, t["id"], "dewi", "cfo_approve").status_code == 403
    assert any(x["id"] == t["id"] for x in c.get("/api/cfo/queue", headers=H("hartono")).json())
    t = act(c, t["id"], "hartono", "cfo_approve").json()
    assert t["status"] == "POSTED"


@pytest.mark.parametrize("name,spv,who,status,expected", [
    ("04_kontrak_C_retensi_dan_pph.pdf", "TRD2", "dewi", "READY", {("OMISI_RETENSI", "MEDIUM"), ("PAJAK_SBU", "MEDIUM")}),
    ("05_kontrak_E_salah_hitung.pdf", "TRD2", "dewi", "DISPUTE", {("MATEMATIKA", "HIGH")}),
    ("06_kontrak_F_nominal_digelembungkan.pdf", "GCT3", "budi", "DISPUTE",
     {("NILAI_TIDAK_SESUAI_PROGRES", "HIGH"), ("FAKTUR_PAJAK", "MEDIUM")}),
    ("07_kontrak_G_klaim_ganda.pdf", "SLO1", "dewi", "HARD_STOP", {("KLAIM_GANDA", "CRITICAL")}),
])
def test_skenario_anomali(c, name, spv, who, status, expected):
    t = upload(c, name, spv, who)
    assert t["status"] == status
    assert codes(t) == expected


def test_hard_stop_hanya_cfo(c):
    t = upload(c, "07_kontrak_G_klaim_ganda.pdf", "SLO1")  # unggah ulang: tetap duplikat
    assert act(c, t["id"], "dewi", "reject", reason="duplikat invoice").status_code == 403
    assert act(c, t["id"], "hartono", "cfo_reject", reason="ditolak").status_code == 422
    assert act(c, t["id"], "hartono", "cfo_reject", reason="double billing dikonfirmasi").json()["status"] == "REJECTED"


def test_override_validasi(c):
    t = upload(c, "05_kontrak_E_salah_hitung.pdf", "TRD2")
    tid = t["id"]
    assert act(c, tid, "dewi", "override", field="progres_disetujui", value="55", reason="pendek").status_code == 422
    assert act(c, tid, "dewi", "override", field="progres_disetujui", value="65",
               reason="lebih dari bukti BAP").status_code == 422
    t = act(c, tid, "dewi", "override", field="progres_disetujui", value="55",
            reason="Sesuai hasil cek lapangan ulang").json()
    assert t["calc_verified"]["p"] == "0.55"


def test_erp_gagal_lalu_kirim_ulang(c):
    ready = [x for x in c.get("/api/queue?spv=GCT3", headers=H("budi")).json()
             if x["kind"] == "AP" and x["status"] == "READY"]
    tid = ready[0]["id"]
    c.post("/api/demo/erp_fail", json={"on": True}, headers=H("budi"))
    assert act(c, tid, "budi", "post").json()["status"] == "ERP_GAGAL"
    c.post("/api/demo/erp_fail", json={"on": False}, headers=H("budi"))
    t = act(c, tid, "budi", "resend").json()
    assert t["status"] == "POSTED" and t["erp_ref"]


def test_uj2_rekonsiliasi(c):
    with open(seedmod.DEMO / "rekening_koran_SLO1_2026-10-17.csv", "rb") as f:
        raw = f.read()
    stats = c.post("/api/ar/upload", data={"spv": "SLO1"}, files={"file": ("rk.csv", raw, "text/csv")},
                   headers=H("andi")).json()
    assert stats["auto"] == 6 and stats["duplicates"] == 1
    rows = list(csv.DictReader(io.StringIO(raw.decode())))
    queue = [x for x in c.get("/api/queue?spv=SLO1", headers=H("andi")).json() if x["kind"] == "AR"]
    by_memo = {x["ref"]: x for x in queue if x["at"]}
    # SM-3: semua baris berkode unit -> RECOMMENDED pada unit yang benar
    coded = [r for r in rows if not r["no_va"] and any(ch.isdigit() for ch in r["berita"])
             and "CLUSTER C1" not in r["berita"]]  # baris Hendra sengaja ambigu (tanpa nomor unit)
    ok = 0
    for r in coded:
        d = c.get(f"/api/ar/receipt/{by_memo[r['berita']]['id']}", headers=H("andi")).json()
        ok += d["status"] == "RECOMMENDED"
    assert ok / len(coded) >= 0.95
    hendra = by_memo["TRF HENDRA GUNAWAN CLUSTER C1"]
    assert hendra["status"] == "MANUAL_REVIEW"

    sut = c.get(f"/api/ar/receipt/{by_memo['TRF BPK SUTRISNO BLK C1/02']['id']}", headers=H("andi")).json()
    assert sut["status"] == "RECOMMENDED" and sut["selected_unit"]["code"] == "C1-02"
    assert sut["preview"]["lines"][0]["late_days"] == 12 and int(sut["preview"]["total_denda"]) > 0
    r = c.post(f"/api/ar/receipt/{sut['id']}/confirm", headers=H("andi"),
               json={"unit_id": sut["selected_unit"]["id"],
                     "waiver": {"reason": "Mortgage disbursement", "justification": "Waiting for BTN mortgage"}}).json()
    assert r["status"] == "ALLOCATED" and r["penalty_status"] == "WAIVED" and len(r["outbox"]) == 2
    assert c.post(f"/api/ar/receipt/{sut['id']}/confirm", headers=H("andi"),
                  json={"unit_id": sut["selected_unit"]["id"]}).status_code == 422


def test_waiver_eksekutif_butuh_cfo(c):
    q = [x for x in c.get("/api/queue?spv=SLO1", headers=H("andi")).json()
         if x["kind"] == "AR" and x["status"] == "RECOMMENDED"]
    d = c.get(f"/api/ar/receipt/{q[0]['id']}", headers=H("andi")).json()
    r = c.post(f"/api/ar/receipt/{d['id']}/confirm", headers=H("andi"),
               json={"unit_id": d["selected_unit"]["id"],
                     "waiver": {"reason": "Executive authority", "justification": "Priority customer"}}).json()
    assert r["penalty_status"] == "MENUNGGU_CFO"
    assert c.post(f"/api/cfo/waiver/{d['id']}", json={"approve": True}, headers=H("andi")).status_code == 403
    assert c.post(f"/api/cfo/waiver/{d['id']}", json={"approve": False, "reason": "tidak memenuhi syarat"},
                  headers=H("hartono")).json()["penalty_status"] == "DITAGIH"


def test_jejak_audit_tamper_evident(c):
    assert c.get("/api/audit/verify", headers=H("hartono")).json()["ok"]
    assert c.get("/api/audit/verify", headers=H("dewi")).status_code == 403
    c.post("/api/demo/tamper", headers=H("hartono"))
    assert not c.get("/api/audit/verify", headers=H("hartono")).json()["ok"]


def test_dashboard(c):
    d = c.get("/api/dashboard?spv=ALL", headers=H("hartono")).json()
    assert d["unallocated_ar"] > 0 and d["flagged"] >= 1 and d["velocity_min"] is not None
    assert d["leakage_prevented"] > 0


def test_gemini_gagal_beralih_ke_pembaca_offline(c, monkeypatch):
    from app import extractor as ex

    def boom(pages):
        raise RuntimeError("Gemini quota exhausted (429).")

    monkeypatch.setenv("GEMINI_MODE", "gemini")
    monkeypatch.setattr(ex, "_gemini", boom)
    t = upload(c, "05_kontrak_E_salah_hitung.pdf", "TRD2")
    assert t["status"] != "GAGAL_PROSES" and t["fallback"].startswith("Gemini quota")
    assert any("Switching" in e["msg"] for e in t["telemetry"])
