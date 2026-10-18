"""Cek cepat alur demo standar di situs yang sudah di-deploy, lalu kembalikan ke data bersih.

    uv run python scripts/standard_check.py https://omniaudit-....run.app

Langkah: reset standar -> UJ-1 (overbilling, posting) -> UJ-3 (kasus CFO) -> UJ-2 (rekening koran + waiver)
-> verifikasi jejak audit -> reset standar lagi. Memakai 2 request Gemini.
"""
import sys
import time
from pathlib import Path

import httpx

URL = sys.argv[1].rstrip("/")
DEMO = Path(__file__).resolve().parents[2] / "demo"
fails: list[str] = []


def H(p):
    return {"X-Persona": p}


def check(cond, msg):
    print(("  OK    " if cond else "  GAGAL ") + msg)
    if not cond:
        fails.append(msg)


def upload(c, name, spv, who="dewi"):
    with open(DEMO / name, "rb") as f:
        r = c.post("/api/ap/upload", data={"spv": spv}, files={"file": (name, f, "application/pdf")}, headers=H(who))
    r.raise_for_status()
    tid = r.json()["id"]
    for _ in range(150):
        t = c.get(f"/api/ap/termin/{tid}", headers=H(who)).json()
        if t["status"] != "PROCESSING":
            return t
        time.sleep(2)
    return t


def act(c, tid, who, action, **kw):
    return c.post(f"/api/ap/termin/{tid}/action", json={"action": action, **kw}, headers=H(who)).json()


with httpx.Client(base_url=URL, timeout=300) as c:
    print(f"Situs: {URL}")
    check(c.post("/api/demo/reset", json={"mode": "standard"}, headers=H("hartono")).status_code == 200, "reset ke demo standar")
    meta = c.get("/api/meta").json()
    print(f"  mode: {meta['mode']} ({meta['model']})")

    print("UJ-1 overbilling (Dewi)")
    t = upload(c, "01_UJ1_kontrak_B_overbilling.pdf", "SLO1")
    codes = sorted({a["code"] for a in t["anomalies"]})
    check(t["status"] == "DISPUTE" and codes == ["OVERBILLING"], f"unggah: {t['status']} {codes}")
    check(t["calc_verified"].get("net") == "234562500", f"net payable terverifikasi {t['calc_verified'].get('net')}")
    t = act(c, t["id"], "dewi", "post")
    check(t["status"] == "POSTED" and bool(t["erp_ref"]), f"posting ke ERP: {t['status']} {t['erp_ref']}")

    print("UJ-3 kasus CFO (Dewi -> Hartono)")
    t = upload(c, "02_UJ3_kontrak_A_butuh_CFO.pdf", "SLO1")
    check(t["status"] == "DISPUTE" and t["needs_cfo"], f"unggah: {t['status']}, butuh CFO {t['needs_cfo']}")
    t = act(c, t["id"], "dewi", "submit_cfo")
    check(t["status"] == "MENUNGGU_CFO", f"ajukan ke CFO: {t['status']}")
    t = act(c, t["id"], "hartono", "cfo_approve")
    check(t["status"] == "POSTED" and t["calc_verified"]["net"] == "2112875000", f"CFO setuju: {t['status']} net {t['calc_verified']['net']}")

    print("UJ-2 rekonsiliasi (Andi)")
    with open(DEMO / "rekening_koran_SLO1_2026-10-17.csv", "rb") as f:
        stats = c.post("/api/ar/upload", data={"spv": "SLO1"}, files={"file": ("rk.csv", f, "text/csv")}, headers=H("andi")).json()
    check(stats.get("rows") == 29 and stats.get("auto") == 6, f"unggah CSV: {stats}")
    q = [x for x in c.get("/api/queue?spv=SLO1", headers=H("andi")).json() if x["kind"] == "AR"]
    sut = next(x for x in q if x["ref"] == "TRF BPK SUTRISNO BLK C1/02")
    d = c.get(f"/api/ar/receipt/{sut['id']}", headers=H("andi")).json()
    check(d["status"] == "RECOMMENDED" and d["selected_unit"]["code"] == "C1-02", f"Sutrisno -> {d['selected_unit']['code']} ({d['status']})")
    r = c.post(f"/api/ar/receipt/{sut['id']}/confirm", headers=H("andi"), json={
        "unit_id": d["selected_unit"]["id"],
        "waiver": {"reason": "Mortgage disbursement", "justification": "Waiting for BTN mortgage disbursement"}}).json()
    check(r["status"] == "ALLOCATED" and r["penalty_status"] == "WAIVED" and len(r["outbox"]) == 2,
          f"alokasi + waiver + notifikasi: {r['status']} {r['penalty_status']} {len(r['outbox'])} pesan")
    k = c.get(f"/api/outbox/{r['outbox'][0]['id']}/attachment?persona=andi")
    check(k.status_code == 200 and k.headers["content-type"] == "application/pdf", "kuitansi PDF bisa dibuka")

    print("CFO")
    v = c.get("/api/audit/verify", headers=H("hartono")).json()
    check(v["ok"], f"jejak audit utuh ({v['checked']} entri)")
    check(c.post("/api/demo/reset", json={"mode": "standard"}, headers=H("hartono")).status_code == 200,
          "dikembalikan ke demo standar (bersih untuk rekaman)")

print()
print(f"{len(fails)} GAGAL" if fails else "Semua alur demo standar berjalan.")
sys.exit(1 if fails else 0)
