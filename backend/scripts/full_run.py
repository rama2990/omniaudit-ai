"""Simulasi full run: jalankan semua langkah demo/full-run/skenario.json lewat API dan cocokkan hasilnya.

    uv run python scripts/full_run.py           database sementara (aman, tidak menyentuh data server)
    uv run python scripts/full_run.py --live    ke database server; jalankan dulu `python -m app.seed --full-run`

Mode Gemini mengikuti backend/.env (GEMINI_MODE=auto memakai Gemini bila GEMINI_API_KEY ada).
"""
import argparse
import json
import os
import sys
import tempfile
import time

ap = argparse.ArgumentParser()
ap.add_argument("--live", action="store_true", help="pakai database server (hasil terlihat di aplikasi)")
ap.add_argument("--offline", action="store_true", help="paksa pembaca pola teks lokal (tidak memakai kuota Gemini)")
args = ap.parse_args()
if args.offline:
    os.environ["GEMINI_MODE"] = "fake"
if not args.live:
    tmp = tempfile.mkdtemp(prefix="omni-fullrun-")
    os.environ["OMNI_DATA"] = os.path.join(tmp, "data")
    os.environ["OMNI_DEMO"] = os.path.join(tmp, "demo")
os.environ.setdefault("OMNI_TELEMETRY_DELAY", "0")

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import select  # noqa: E402

from app import extractor  # noqa: E402
from app.db import session  # noqa: E402
from app.models import Termin  # noqa: E402
from app.seed import DEMO, seed  # noqa: E402

if args.live:
    with session() as s:
        if s.exec(select(Termin).where(Termin.uploaded_by != "arsip")).first():
            sys.exit("Database server sudah berisi tagihan. Jalankan dulu: uv run python -m app.seed --full-run")
else:
    print("Menyiapkan database sementara (data master + dokumen full run)…")
    seed(full_run=True)

from app.main import app  # noqa: E402

FR = DEMO / "full-run"
spec = json.loads((FR / "skenario.json").read_text(encoding="utf-8"))
fails: list[str] = []


def check(step, cond, msg):
    if not cond:
        fails.append(f"{step}: {msg}")
    return cond


def H(p):
    return {"X-Persona": p}


def rp(n):
    return "Rp" + f"{int(n):,}".replace(",", ".")


with TestClient(app) as c:
    print(f"Mode ekstraksi: {extractor.mode()}  |  dokumen: {FR}")
    if extractor.mode() == "gemini":
        print(f"Catatan: memakai {len(spec['ap'])} request Gemini (kuota gratis: sekitar 20 per hari per model).")
    print()
    print("TAGIHAN KONTRAKTOR (AP)")
    for st in spec["ap"]:
        sid, n0 = st["id"], len(fails)
        t0 = time.time()
        with open(FR / st["file"], "rb") as f:
            r = c.post("/api/ap/upload", data={"spv": st["spv"]}, files={"file": (st["file"], f, "application/pdf")},
                       headers=H(st["persona"]))
        if not check(sid, r.status_code == 200, f"unggah gagal: {r.text}"):
            continue
        tid = r.json()["id"]
        t = c.get(f"/api/ap/termin/{tid}", headers=H(st["persona"])).json()
        e = st["expect"]
        codes = sorted({a["code"] for a in t["anomalies"]})
        check(sid, t["status"] == e["status"], f"status {t['status']} (harap {e['status']})"
                                               + (f": {t['error']}" if t.get("error") else ""))
        if "codes" in e:
            check(sid, codes == sorted(e["codes"]), f"temuan {codes} (harap {sorted(e['codes'])})")
        if "codes_any" in e:
            check(sid, set(codes) <= set(e["codes_any"]), f"temuan {codes} di luar {e['codes_any']}")
        if "needs_cfo" in e:
            check(sid, t["needs_cfo"] == e["needs_cfo"], f"butuh CFO = {t['needs_cfo']}")
        first = f"{t['status']} [{', '.join(codes) or '-'}] skor {float(t['confidence']):.0%}"
        for a in st["actions"]:
            if a["do"] == "erp_fail":
                c.post("/api/demo/erp_fail", json={"on": a["on"]}, headers=H("dewi"))
                continue
            body = {"action": a["do"], "reason": a.get("reason", "")}
            if a["do"] == "override":
                body.update(field=a["field"], value=a["value"])
            if a["do"] == "set_contract":
                cs = c.get(f"/api/ap/contracts?spv={st['spv']}", headers=H(a["by"])).json()
                body["contract_id"] = next(x["id"] for x in cs if x["no"] == a["contract"])
            r = c.post(f"/api/ap/termin/{tid}/action", json=body, headers=H(a["by"]))
            if not check(sid, r.status_code == 200, f"aksi {a['do']} oleh {a['by']}: {r.status_code} {r.text[:160]}"):
                break
            t = r.json()
            if a.get("expect"):
                check(sid, t["status"] == a["expect"], f"setelah {a['do']}: {t['status']} (harap {a['expect']})")
        c.post("/api/demo/erp_fail", json={"on": False}, headers=H("dewi"))  # jangan bocor ke langkah berikutnya
        f = st["final"]
        check(sid, t["status"] == f["status"], f"status akhir {t['status']} (harap {f['status']})")
        cv = t.get("calc_verified") or {}
        for k in ("net", "pen", "pen_left"):
            if k in f:
                check(sid, cv and int(cv[k]) == f[k], f"{k} {cv.get(k)} (harap {f[k]})")
        mark = "OK " if len(fails) == n0 else "GAGAL"
        net = f", Net Payable {rp(cv['net'])}" if cv and t["status"] == "POSTED" else ""
        print(f"  {mark} {sid} {st['judul']}\n        unggah: {first} | akhir: {t['status']}{net} ({time.time() - t0:.1f} dtk)")

    print("\nPENERIMAAN PEMBELI (AR)")
    for st in spec["ar"]:
        sid, n0, who = st["id"], len(fails), st["persona"]
        with open(FR / st["file"], "rb") as f:
            r = c.post("/api/ar/upload", data={"spv": st["spv"]}, files={"file": (st["file"], f, "text/csv")}, headers=H(who))
        if not check(sid, r.status_code == 200, f"unggah gagal: {r.text}"):
            continue
        stats = r.json()
        check(sid, stats == st["expect"], f"ringkasan {stats} (harap {st['expect']})")
        queue = [x for x in c.get(f"/api/queue?spv={st['spv']}", headers=H(who)).json() if x["kind"] == "AR"]
        for d in st["decisions"]:
            hit = [x for x in queue if x["ref"] == d["memo"] and x["status"] != "ALLOCATED"]
            if not check(sid, hit, f"baris '{d['memo']}' tidak ditemukan"):
                continue
            rid = hit[0]["id"]
            det = c.get(f"/api/ar/receipt/{rid}", headers=H(who)).json()
            check(sid, det["status"] == d["status"], f"'{d['memo']}' status {det['status']} (harap {d['status']})")
            unit = next((x["unit_id"] for x in det["candidates"] if x["code"] == d["unit"]), None) or \
                c.get(f"/api/ar/units?spv={st['spv']}&q={d['unit']}", headers=H(who)).json()[0]["id"]
            body = {"unit_id": unit, "waiver": {"reason": d["waiver"][0], "justification": d["waiver"][1]} if d.get("waiver") else None}
            r = c.post(f"/api/ar/receipt/{rid}/confirm", json=body, headers=H(who))
            if not check(sid, r.status_code == 200, f"konfirmasi '{d['memo']}': {r.text[:160]}"):
                continue
            res = r.json()
            check(sid, res["selected_unit"]["code"] == d["unit"], f"'{d['memo']}' masuk ke {res['selected_unit']['code']}")
            if d.get("penalty"):
                check(sid, res["penalty_status"] == d["penalty"], f"'{d['memo']}' denda {res['penalty_status']} (harap {d['penalty']})")
            if d.get("settled") is False:
                check(sid, not res["allocation"]["lines"][0]["settled"], f"'{d['memo']}' seharusnya terbayar sebagian")
            if d.get("selisih"):
                check(sid, int(res["allocation"]["selisih_transfer"]) == d["selisih"], f"'{d['memo']}' selisih transfer")
            check(sid, len(res["outbox"]) == 2, f"'{d['memo']}' notifikasi {len(res['outbox'])}")
            if d.get("cfo"):
                r = c.post(f"/api/cfo/waiver/{rid}", json={"approve": d["cfo"]["approve"], "reason": "Disetujui CFO"},
                           headers=H(d["cfo"]["by"]))
                check(sid, r.status_code == 200 and r.json()["penalty_status"] == d["cfo"]["penalty"], f"keputusan CFO: {r.text[:120]}")
        mark = "OK " if len(fails) == n0 else "GAGAL"
        print(f"  {mark} {sid} {st['judul']}\n        {stats['rows']} baris: {stats['auto']} otomatis, {stats['recommended']} siap, "
              f"{stats['manual']} manual; {len(st['decisions'])} keputusan dijalankan")

    print("\nAKHIR")
    cfo = c.get("/api/cfo/queue", headers=H("hartono")).json()
    check("AKHIR", not cfo, f"antrean CFO masih berisi {len(cfo)} item")
    v = c.get("/api/audit/verify", headers=H("hartono")).json()
    check("AKHIR", v["ok"], "rantai hash jejak audit putus")
    d = c.get("/api/dashboard?spv=ALL", headers=H("hartono")).json()
    print(f"  Antrean CFO kosong: {not cfo} | jejak audit utuh: {v['ok']} ({v['checked']} entri)")
    print(f"  Kebocoran dicegah: {rp(d['leakage_prevented'])} | dana belum teralokasi: {rp(d['unallocated_ar'])}")

print()
if fails:
    print(f"{len(fails)} pemeriksaan GAGAL:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("Semua langkah full run sesuai skenario.")
