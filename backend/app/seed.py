"""Data seed + file demo. Jalankan: uv run python -m app.seed  (opsi --fast: lewati PDF scan & pra-proses)."""
import csv
import os
import random
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

from sqlmodel import select

from app import ar, auditlog
from app.audit import AP, AR, CFO, norm_invoice
from app.calc import ContractTerms, PostedHistory, compute_termin, pph_rate
from app.db import DATA, ROOT, init_db, session
from app.journal import ap_journal
from app.models import Contract, Installment, JournalBatch, Persona, Spv, Termin, Unit, Vendor
from app.samples import Package, build

DEMO = Path(os.getenv("OMNI_DEMO", ROOT.parent / "demo"))
SPVS = [("SLO1", "PT Suburban Land One"), ("TRD2", "PT Tower Residence Dua"), ("GCT3", "PT Garden City Tiga")]
PERSONAS = [
    ("dewi", "Dewi Anggraini", AP, "Finance AP Lead", ["SLO1", "TRD2"]),
    ("budi", "Budi Santoso", AP, "Finance AP Lead", ["GCT3"]),
    ("andi", "Andi Pratama", AR, "Sales Admin & Collection Lead", ["SLO1", "TRD2"]),
    ("sari", "Sari Wulandari", AR, "Sales Admin & Collection Lead", ["GCT3"]),
    ("hartono", "Hartono Wijaya", CFO, "Chief Financial Officer", ["SLO1", "TRD2", "GCT3"]),
]
# (nama, NPWP 15 digit, jenis, sbu)
VENDORS = [
    ("PT Bangun Karya Mandiri", "123456789012345", "PELAKSANAAN", "MENENGAH"),
    ("CV Sinar Konstruksi", "234567890120001", "PELAKSANAAN", "KECIL"),
    ("PT Arsitek Nusantara", "345678901230002", "PERENCANAAN", "KECIL"),
    ("PT Pengawas Prima", "456789012340003", "PENGAWASAN", "TANPA"),
    ("PT Beton Jaya Abadi", "567890123450004", "PELAKSANAAN", "TANPA"),
    ("PT Integra Bangun Persada", "678901234560005", "TERINTEGRASI", "BESAR"),
]
# key: (spv, no, nama, vendor_idx, dpp, um%, target, [progres posted kumulatif], invoice terakhir)
CONTRACTS = {
    "A": ("SLO1", "SPK/SLO/2026/001", "Pembangunan Cluster Magnolia (120 unit)", 0, 10_000_000_000, "0.10", date(2026, 9, 30), ["0.25", "0.50"], None),
    "B": ("SLO1", "SPK/SLO/2026/002", "Pekerjaan Struktur Cluster C1", 1, 1_500_000_000, "0", date(2026, 12, 31), ["0.20", "0.40"], None),
    "C": ("TRD2", "SPK/TRD/2026/003", "Pekerjaan Fondasi Tower B", 4, 4_000_000_000, "0", date(2027, 3, 31), ["0.20"], None),
    "D": ("GCT3", "SPK/GCT/2026/004", "Design & Build Clubhouse Garden City", 5, 2_200_000_000, "0.10", date(2027, 2, 28), ["0.30"], None),
    "E": ("TRD2", "SPK/TRD/2026/005", "Jasa Perencanaan Tower C", 2, 800_000_000, "0", date(2027, 6, 30), ["0.40"], None),
    "F": ("GCT3", "SPK/GCT/2026/006", "Jasa Pengawasan Konstruksi Garden City", 3, 600_000_000, "0", date(2027, 6, 30), ["0.50"], None),
    "G": ("SLO1", "SPK/SLO/2026/007", "Infrastruktur Jalan Cluster Magnolia", 0, 3_000_000_000, "0", date(2027, 1, 31), ["0.20"], None),
    "H": ("TRD2", "SPK/TRD/2026/008", "Pekerjaan Struktur Tower A", 0, 5_000_000_000, "0", date(2027, 4, 30), ["0.15", "0.30"], "INV/BKM/2026/077"),
}
NAMES = ["Rina Kartika", "Sutrisno Wibowo", "Hendra Gunawan", "Hendra Gunawan", "Agus Salim", "Bambang Sudrajat",
         "Siti Rahmawati", "Yusuf Hidayat", "Maria Christina", "Fajar Nugroho", "Lina Marlina", "Rudi Hartono",
         "Nur Aisyah", "Teguh Prasetyo", "Wulan Sari", "Indra Kusuma", "Ratna Dewi", "Joko Susilo", "Melati Puspita",
         "Hadi Purnomo", "Ayu Lestari", "Dimas Saputra", "Fitri Handayani", "Eko Wahyudi", "Putri Maharani",
         "Arif Rahman", "Novi Anggraini", "Rizky Ramadhan", "Diana Puspitasari", "Gilang Permana", "Sri Mulyani",
         "Andreas Tanoto", "Kevin Halim", "Yohana Siregar", "Benny Situmorang", "Clara Wijaya", "Robert Sihombing",
         "Lia Amalia", "Ferry Irawan", "Tina Melinda", "Budi Hartanto", "Yanti Susanti", "Doni Firmansyah",
         "Mega Utami", "Irfan Hakim", "Laras Ayuningtyas", "Samuel Gultom", "Vina Oktaviani", "Heru Santoso",
         "Citra Kirana", "Bayu Aji", "Nadia Safitri", "Reza Pahlevi", "Anita Rachman", "Wawan Setiawan",
         "Galih Pratama", "Ika Natalia", "Johan Effendi", "Hana Pertiwi", "Yoga Wicaksono"]


def npwp_fmt(d15: str) -> str:
    return f"{d15[0:2]}.{d15[2:5]}.{d15[5:8]}.{d15[8]}-{d15[9:12]}.{d15[12:15]}"


def unit_codes():
    slo = [f"{c}-{n:02d}" for c in ("C1", "C2", "D1", "D2") for n in range(1, 9)]
    trd = [f"A-{f}-{n:02d}" for f in (10, 11, 12) for n in range(1, 5)]
    gct = [f"G1-{n:02d}" for n in range(1, 17)]
    return [("SLO1", c) for c in slo] + [("TRD2", c) for c in trd] + [("GCT3", c) for c in gct]


SLO_BEHIND = {5, 12}  # Sep+Okt belum dibayar
SLO_AHEAD = set(range(20, 26))  # Okt sudah dibayar (bayar Nov lebih awal via VA)


def sample_packages(contracts: dict[str, Contract], vendors: list[Vendor]) -> dict[str, tuple[Package, str, bool]]:
    def v(key):
        return VENDORS[CONTRACTS[key][3]]

    def pkg(key, inv, klaim, bap, tgl, items, ppn, bruto, ret, pph, faktur=True, proyek=None):
        name, d15 = v(key)[0], v(key)[1]
        return Package(vendor=name, npwp=npwp_fmt(d15), invoice_no=inv, contract_no=CONTRACTS[key][1], tanggal=tgl,
                       progres_klaim=klaim, line_items=items, ppn=ppn, bruto=bruto, progres_bap=bap, tanggal_bap=tgl,
                       proyek=proyek or CONTRACTS[key][2], retensi=ret, pph=pph,
                       faktur={"nsfp": f"010.000-26.{random.Random(inv).randint(10**7, 10**8 - 1)}",
                               "npwp": npwp_fmt(d15), "dpp": sum(a for _, a in items), "ppn": ppn} if faktur else None)

    return {
        "01_UJ1_kontrak_B_overbilling.pdf": (pkg("B", "INV/SK/2026/031", "60", "55", "12-10-2026",
            [("Pekerjaan Struktur Cluster C1 Tahap 3", 180_000_000), ("Pekerjaan Atap Cluster C1", 120_000_000)],
            33_000_000, 333_000_000, 15_000_000, ("1,75", 5_250_000)), "B", False),
        "02_UJ3_kontrak_A_butuh_CFO.pdf": (pkg("A", "INV/BKM/2026/088", "80", "75", "10-10-2026",
            [("Pekerjaan Struktur Magnolia Tahap 3 (net uang muka)", 1_800_000_000),
             ("Pekerjaan MEP Magnolia Tahap 2 (net uang muka)", 900_000_000)],
            297_000_000, 2_997_000_000, 150_000_000, ("2,65", 71_550_000)), "A", False),
        "03_kontrak_D_bersih_scan.pdf": (pkg("D", "INV/IBP/2026/019", "45", "45", "14-10-2026",
            [("Design & Build Clubhouse Tahap 2 (net uang muka)", 297_000_000)],
            32_670_000, 329_670_000, 16_500_000, ("2,65", 7_870_500)), "D", True),
        "04_kontrak_C_retensi_dan_pph.pdf": (pkg("C", "INV/BJA/2026/042", "30", "30", "15-10-2026",
            [("Pekerjaan Bored Pile Tower B", 250_000_000), ("Pekerjaan Pile Cap Tower B", 150_000_000)],
            44_000_000, 444_000_000, None, ("2,65", 10_600_000)), "C", False),
        "05_kontrak_E_salah_hitung.pdf": (pkg("E", "INV/AN/2026/015", "60", "60", "15-10-2026",
            [("Gambar Kerja Struktur Tower C", 100_000_000), ("Gambar Kerja MEP Tower C", 50_000_000)],
            17_600_000, 177_600_000, 8_000_000, ("3,50", 5_600_000)), "E", False),
        "06_kontrak_F_nominal_digelembungkan.pdf": (pkg("F", "INV/PP/2026/027", "70", "70", "16-10-2026",
            [("Jasa Pengawasan Bulan September-Oktober", 150_000_000)],
            16_500_000, 166_500_000, 7_500_000, ("6,00", 9_000_000)), "F", False),
        "07_kontrak_G_klaim_ganda.pdf": (pkg("G", "INV/BKM/2026/077", "35", "35", "16-10-2026",
            [("Pekerjaan Jalan Cluster Magnolia Tahap 2", 450_000_000)],
            49_500_000, 499_500_000, 22_500_000, ("2,65", 11_925_000)), "G", False),
    }


def seed(fast: bool = False, full_run: bool = False):
    """fast: tanpa PDF scan & pra-proses (tes). full_run: data master saja, untuk demo/full-run/SKENARIO.md."""
    os.environ.setdefault("OMNI_TELEMETRY_DELAY", "0")
    init_db(reset=True)
    for sub in ("uploads", "kuitansi"):
        shutil.rmtree(DATA / sub, ignore_errors=True)
    rnd = random.Random(7)
    with session() as s:
        for i, n in SPVS:
            s.add(Spv(id=i, name=n))
        for pid, name, role, title, spvs in PERSONAS:
            s.add(Persona(id=pid, name=name, role=role, title=title, spvs=spvs))
        vendors = []
        for name, d15, jenis, sbu in VENDORS:
            v = Vendor(name=name, npwp="0" + d15, jenis=jenis, sbu=sbu)
            s.add(v)
            vendors.append(v)
        s.flush()

        contracts: dict[str, Contract] = {}
        hist_time = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
        for key, (spv, no, name, vi, dpp, um, target, posted, last_inv) in CONTRACTS.items():
            c = Contract(spv_id=spv, no=no, no_norm=norm_invoice(no), name=name, vendor_id=vendors[vi].id,
                         dpp_kontrak=dpp, um_pct=um, target_date=target)
            s.add(c)
            s.flush()
            contracts[key] = c
            terms = ContractTerms(dpp_kontrak=D(dpp), pph_rate=pph_rate(vendors[vi].jenis, vendors[vi].sbu),
                                  target_date=target, um_pct=D(um))
            h = PostedHistory()
            for k, p in enumerate(posted):
                bap = min(target, date(2026, 5 + 2 * k, 20)) - timedelta(days=1)
                calc = compute_termin(terms, h, D(p), bap)
                h = PostedHistory(h.np_sum + calc.np, h.um_sum + calc.um, h.pen_sum + calc.pen)
                hist_time += timedelta(days=rnd.randint(9, 14), minutes=rnd.randint(0, 300))
                if k == len(posted) - 1:  # termin terakhir diposting baru-baru ini (untuk Recon Velocity)
                    hist_time = datetime(2026, 9, 20 + list(CONTRACTS).index(key) % 9, 10, rnd.randint(0, 59), tzinfo=timezone.utc)
                inv = last_inv if (last_inv and k == len(posted) - 1) else f"INV/{key}/2026/{k + 1:03d}"
                t = Termin(spv_id=spv, contract_id=c.id, status="POSTED", filename=f"arsip-{inv.replace('/', '-')}.pdf",
                           uploaded_by="arsip", uploaded_at=hist_time,
                           processed_at=hist_time + timedelta(minutes=1),
                           posted_at=hist_time + timedelta(minutes=rnd.randint(6, 14)),
                           invoice_norm=norm_invoice(inv), npwp_norm=vendors[vi].npwp, confidence="0.97",
                           calc_claim=calc.as_dict(), calc_verified=calc.as_dict(),
                           erp_ref=f"ERP-{hist_time:%Y%m%d}-{rnd.randint(0, 0xFFFFFF):06X}",
                           extraction={"fields": {}, "line_items": [], "page_types": {}, "mode": "arsip"})
                s.add(t)
                s.flush()
                s.add(JournalBatch(spv_id=spv, source="AP", source_id=t.id, erp_ref=t.erp_ref, created_at=t.posted_at,
                                   lines=[{"side": x.side, "account": x.account, "amount": int(x.amount)}
                                          for x in ap_journal(calc)]))

        # Unit & angsuran
        units_by_spv: dict[str, list[Unit]] = {}
        for idx, (spv, code) in enumerate(unit_codes()):
            name = NAMES[idx % len(NAMES)]
            local = len(units_by_spv.get(spv, []))
            u = Unit(spv_id=spv, code=code, buyer=name, va=f"8808{SPVS.index((spv, dict(SPVS)[spv])) + 1}{local + 1:04d}",
                     phone=f"0812{rnd.randint(10**7, 10**8 - 1)}", email=name.lower().replace(" ", ".") + "@contoh.id")
            s.add(u)
            s.flush()
            units_by_spv.setdefault(spv, []).append(u)
            amount = 8_750_000 if code in ("C1-03", "C1-04") else rnd.randrange(5_000_000, 15_000_001, 100_000)
            paid_until = 9
            if spv == "SLO1" and local in SLO_BEHIND:
                paid_until = 8
            if spv == "SLO1" and local in SLO_AHEAD:
                paid_until = 10
            for seq in range(1, 25):
                due = date(2026 + (seq - 1) // 12, (seq - 1) % 12 + 1, 5)
                s.add(Installment(unit_id=u.id, seq=seq, due=due, amount=amount,
                                  paid=amount if seq <= paid_until else 0))
        s.commit()

        csvs = write_csvs(s, units_by_spv)
        packages = sample_packages(contracts, vendors)
        DEMO.mkdir(exist_ok=True)
        for fname, (pkg, _, raster) in packages.items():
            build(pkg, DEMO / fname, raster=raster and not fast)

        # Pra-muat rekening koran kemarin (10-16) untuk tiap SPV
        for spv, path in csvs["preload"].items():
            ar.ingest_csv(s, spv, path.read_text(encoding="utf-8"), "andi" if spv != "GCT3" else "sari", AR)
        s.commit()
        from app import fullrun
        fullrun.build(s, units_by_spv, DEMO, scan=not fast)

    if not fast and not full_run:  # pra-proses PDF 03..07 agar antrean berisi; 01 & 02 untuk demo live
        from app.pipeline import process_termin
        for fname, (pkg, key, _) in packages.items():
            if fname.startswith(("01", "02")):
                continue
            tid = new_upload(contracts[key].spv_id, DEMO / fname, "dewi" if contracts[key].spv_id != "GCT3" else "budi")
            process_termin(tid)
    with session() as s:
        auditlog.record(s, actor="system", role="SYSTEM", spv_id="*", action="SEED", entity="system", entity_id=0)
        s.commit()
    print(f"Seed selesai. Database: {DATA / 'omniaudit.db'}. File demo: {DEMO}")


def regemini():
    """Seed di-bake saat build image tanpa GEMINI_API_KEY → item antrean terbaca pola teks lokal.
    Saat start dengan Gemini aktif, baca ulang item itu dengan Gemini (OCR sudah tersimpan, jadi cepat)."""
    from app import extractor
    from app.pipeline import FINAL, process_termin
    if extractor.mode() != "gemini":
        return
    with session() as s:
        todo = [(t.id, t.pages) for t in s.exec(select(Termin)).all()
                if t.pages and t.extraction.get("mode") == "fake" and t.status not in FINAL and not t.overrides]
    # ponytail: tanpa lock; aksi user pada item yang sedang dibaca ulang (~1 menit pertama) bisa tertimpa
    for tid, pages in todo:
        try:
            ext = extractor.extract(pages)
        except Exception as e:  # noqa: BLE001 - Gemini gagal → biarkan hasil pola teks lokal
            print(f"regemini termin {tid}: {e}")
            continue
        process_termin(tid, ext)


SNAPSHOTS = {False: Path("/app/seed-data"), True: Path("/app/seed-fullrun")}  # dibuat saat build image


def reset(full_run: bool = False):
    """Kembalikan data demo ke kondisi awal (untuk mengulang take video)."""
    import threading

    from app.db import engine
    engine.dispose()
    snap = SNAPSHOTS[full_run]
    if snap.exists():  # Cloud Run: salin snapshot, beberapa detik
        shutil.rmtree(DATA, ignore_errors=True)
        shutil.copytree(snap, DATA)
    else:  # lokal: bangun ulang dari awal
        seed(full_run=full_run)
    if not full_run:
        threading.Thread(target=regemini, daemon=True).start()


def new_upload(spv_id: str, src: Path, actor: str) -> int:
    with session() as s:
        t = Termin(spv_id=spv_id, filename=src.name, uploaded_by=actor)
        s.add(t)
        s.flush()
        dest = DATA / "uploads" / f"termin-{t.id}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        t.pdf_path = str(dest)
        auditlog.record(s, actor=actor, role=AP, spv_id=spv_id, action="UPLOAD", entity="termin", entity_id=t.id,
                        after={"filename": src.name})
        s.commit()
        return t.id


def _oldest_unpaid(s, u: Unit, n=1) -> int:
    insts = s.exec(select(Installment).where(Installment.unit_id == u.id, Installment.paid < Installment.amount)
                   .order_by(Installment.seq)).all()
    return sum(i.amount - i.paid for i in insts[:n])


FORMATS = [
    lambda first, cl, n, code: f"TRF {first} BLOK {cl} NO {n}",
    lambda first, cl, n, code: f"ANGS OKT {cl}/{n:02d} {first}",
    lambda first, cl, n, code: f"{cl}-{n} {first} CICILAN",
    lambda first, cl, n, code: f"PEMBAYARAN UNIT {cl} {n:02d}",
    lambda first, cl, n, code: f"CICILAN {code} BPK {first}",
]


def write_csvs(s, units_by_spv) -> dict:
    head = ["tanggal", "nama_pengirim", "bank", "nominal", "berita", "referensi", "no_va"]
    banks = ["BCA", "MANDIRI", "BNI", "BRI", "CIMB"]
    rnd = random.Random(11)

    def ref():
        return f"FT{rnd.randint(10**9, 10**10 - 1)}"

    def coded(day, u, k, n_inst=1, fee=0, sender=None):
        cl, n = u.code.rsplit("-", 1)
        first = u.buyer.split()[0].upper()
        memo = FORMATS[k % len(FORMATS)](first, cl, int(n), u.code)
        return [day, sender or u.buyer.upper(), banks[k % 5], _oldest_unpaid(s, u, n_inst) - fee, memo, ref(), ""]

    slo, trd, gct = units_by_spv["SLO1"], units_by_spv["TRD2"], units_by_spv["GCT3"]
    pre = {
        "SLO1": [coded("2026-10-16", slo[30], 0), coded("2026-10-16", slo[31], 1),
                 ["2026-10-16", "CV ANUGERAH", "BCA", 6_200_000, "TRANSFER", "FT5550001111", ""]],
        "TRD2": [["2026-10-16", trd[0].buyer.upper(), "BCA", _oldest_unpaid(s, trd[0]), f"TOWER {trd[0].code}", ref(), ""],
                 ["2026-10-16", trd[1].buyer.upper(), "BNI", _oldest_unpaid(s, trd[1]), "A/10/02 ANGSURAN", ref(), ""],
                 ["2026-10-16", trd[5].buyer.upper(), "BRI", _oldest_unpaid(s, trd[5]), "UNIT A 11 02", ref(), ""],
                 ["2026-10-16", trd[9].buyer.upper(), "MANDIRI", _oldest_unpaid(s, trd[9]), "TWR A 12 2", ref(), ""],
                 ["2026-10-16", trd[3].buyer.upper(), "BCA", _oldest_unpaid(s, trd[3]), "VA", ref(), trd[3].va],
                 ["2026-10-16", "IBU MARTHA", "BCA", 12_500_000, "PEMBAYARAN APARTEMEN", ref(), ""]],
        "GCT3": [coded("2026-10-16", gct[i], i) for i in (0, 2, 4, 7)]
                + [["2026-10-16", gct[9].buyer.upper(), "BCA", _oldest_unpaid(s, gct[9]), "VA", ref(), gct[9].va],
                   ["2026-10-16", "PT SENTOSA", "MANDIRI", 15_000_000, "TRANSFER DANA", ref(), ""]],
    }
    demo = [["2026-10-17", "BPK SUTRISNO", "BCA", _oldest_unpaid(s, slo[1]), "TRF BPK SUTRISNO BLK C1/02", ref(), ""]]
    for k, i in enumerate([0, 4, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18]):
        demo.append(coded("2026-10-17", slo[i], k, fee=150_000 if i in (8, 15) else 0))
    for k, i in enumerate(sorted(SLO_BEHIND)):
        demo.append(coded("2026-10-17", slo[i], k + 2, n_inst=2))
    for i in sorted(SLO_AHEAD):
        demo.append(["2026-10-17", slo[i].buyer.upper(), "BCA", _oldest_unpaid(s, slo[i]), "VA PAYMENT", ref(), slo[i].va])
    for i in (28, 29):
        demo.append(["2026-10-17", slo[i].buyer.upper(), "MANDIRI", _oldest_unpaid(s, slo[i]), "VA PAYMENT", ref(), slo[i].va])
    demo += [["2026-10-17", "HENDRA GUNAWAN", "BCA", 8_750_000, "TRF HENDRA GUNAWAN CLUSTER C1", ref(), ""],
             ["2026-10-17", "PT MAJU JAYA", "BRI", 7_350_000, "TRANSFER", ref(), ""],
             ["2026-10-17", "IBU RATNA", "BNI", 9_000_000, "PEMBAYARAN RUMAH", ref(), ""],
             pre["SLO1"][2]]  # duplikat dari rekening koran kemarin
    out = {"preload": {}}
    DEMO.mkdir(exist_ok=True)
    for spv, rows in pre.items():
        p = DATA / f"rekening_koran_{spv}_2026-10-16.csv"
        _write(p, head, rows)
        out["preload"][spv] = p
        shutil.copyfile(p, DEMO / p.name)
    _write(DEMO / "rekening_koran_SLO1_2026-10-17.csv", head, demo)
    return out


def _write(path: Path, head, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)


if __name__ == "__main__":
    seed(fast="--fast" in sys.argv, full_run="--full-run" in sys.argv)
