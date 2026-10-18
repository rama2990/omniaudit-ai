"""Paket simulasi full run: 12 dokumen tagihan + 3 rekening koran + skenario langkah demi langkah.

Satu sumber kebenaran: `ap_steps()` dan `ar_steps()` menentukan isi dokumen, aksi pengguna, dan hasil yang
diharapkan. `build()` menulis file ke demo/full-run/, SKENARIO.md (panduan manual), dan skenario.json
(dibaca scripts/full_run.py). Mulai dari database `python -m app.seed --full-run`.
"""
import csv
import json
import random
import shutil
from datetime import date
from pathlib import Path

from sqlmodel import select

from app.docs import Party, TerminDoc, build_doc
from app.models import Installment, Unit

SPV_PARTY = {
    "SLO1": Party("PT Suburban Land One", "01.234.111.0-411.000", "Jl. Boulevard Suburban No. 1, Tangerang"),
    "TRD2": Party("PT Tower Residence Dua", "01.234.222.0-411.000", "Jl. Gatot Subroto Kav. 22, Jakarta Selatan"),
    "GCT3": Party("PT Garden City Tiga", "01.234.333.0-411.000", "Jl. Raya Garden City No. 3, Bekasi"),
}
VENDOR = {
    "BKM": Party("PT Bangun Karya Mandiri", "12.345.678.9-012.345", "Jl. Industri Raya No. 45, Cikarang",
                 "General Contractor, Gedung & Infrastruktur", "Bank Mandiri 123-00-0456789-0 a.n. PT Bangun Karya Mandiri",
                 "Ir. Haryanto Kusuma", "Direktur Utama"),
    "SK": Party("CV Sinar Konstruksi", "23.456.789.0-120.001", "Jl. Melati No. 8, Tangerang",
                "Kontraktor Umum dan Pengadaan", "BCA 456-789-0123 a.n. CV Sinar Konstruksi", "Darmawan Setiadi"),
    "AN": Party("PT Arsitek Nusantara", "34.567.890.1-230.002", "Jl. Kemang Raya No. 12, Jakarta Selatan",
                "Konsultan Perencana", "BNI 0123-456-789 a.n. PT Arsitek Nusantara", "Ar. Melinda Wijaya", "Direktur"),
    "PP": Party("PT Pengawas Prima", "45.678.901.2-340.003", "Jl. Pemuda No. 77, Bekasi",
                "Konsultan Manajemen Konstruksi", "BRI 0345-01-000567-30-1 a.n. PT Pengawas Prima", "Teddy Gunawan", "Direktur"),
    "BJA": Party("PT Beton Jaya Abadi", "56.789.012.3-450.004", "Jl. Raya Narogong Km 12, Bekasi",
                 "Spesialis Pondasi & Struktur Beton", "Bank Mandiri 156-00-0987654-3 a.n. PT Beton Jaya Abadi", "Rudy Hermawan", "Direktur"),
    "IBP": Party("PT Integra Bangun Persada", "67.890.123.4-560.005", "Jl. TB Simatupang Kav. 9, Jakarta Selatan",
                 "Design & Build Contractor", "CIMB Niaga 800-12-3456-7 a.n. PT Integra Bangun Persada", "Lukas Pranata", "Direktur"),
}
R = "Rincian pekerjaan tidak sama dengan total tagihan; vendor diminta merevisi invoice."


def _doc(style, vendor, spv, inv, ref, tgl, proyek, termin, progres, items, ppn, bruto, bap, ret, pph, faktur_um=0,
         inkremental=False, scan=False, photos=None, nsfp_seed=0) -> TerminDoc:
    harga = sum(a for _, a, _ in items if a > 0)
    return TerminDoc(style=style, vendor=VENDOR[vendor], buyer=SPV_PARTY[spv], invoice_no=inv, contract_ref=ref,
                     tanggal=tgl, proyek=proyek, termin_label=termin, progres=progres, items=items, ppn=ppn,
                     bruto=bruto, bap_progres=bap, bap_tanggal=tgl, inkremental=inkremental, retensi=ret, pph=pph,
                     faktur={"nsfp": f"0400260{random.Random(inv + str(nsfp_seed)).randint(10**9, 10**10 - 1)}",
                             "harga": harga, "um": faktur_um, "ppn": ppn},
                     photos=photos or [], scan=scan)


def ap_steps() -> list[dict]:
    d = date
    return [
        dict(id="FR-01", hari="Senin 12 Okt", persona="dewi", spv="SLO1", file="FR-01_SK_kontrak-B_termin-3_overbilling.pdf",
             judul="Overbilling: invoice 60%, BAP fisik 55%",
             doc=_doc("CV", "SK", "SLO1", "INV/SK/2026/031", "SPK/SLO/2026/002", d(2026, 10, 12), "Struktur Cluster C1",
                      "Termin 3", "60", [("Pekerjaan struktur Cluster C1 tahap 3", 180_000_000, ""),
                                         ("Pekerjaan atap Cluster C1", 120_000_000, "")],
                      33_000_000, 333_000_000, "55", 15_000_000, ("1,75", 5_250_000)),
             expect={"status": "DISPUTE", "codes": ["OVERBILLING"], "needs_cfo": False},
             actions=[{"do": "post", "by": "dewi"}], final={"status": "POSTED", "net": 234_562_500}),
        dict(id="FR-02", hari="Senin 12 Okt", persona="dewi", spv="SLO1", file="FR-02_BKM_kontrak-A_termin-3_butuh-CFO.pdf",
             judul="Klaim Rp2,997 M melebihi BAP; wajib persetujuan CFO",
             doc=_doc("KORPORAT", "BKM", "SLO1", "INV/BKM/2026/088", "SPK/SLO/2026/001", d(2026, 10, 10),
                      "Pembangunan Cluster Magnolia (120 unit)", "Termin 3", "80",
                      [("Progres pekerjaan struktur & MEP (50% s.d. 80%)", 3_000_000_000, ""),
                       ("Potongan pengembalian uang muka 10%", -300_000_000, "")],
                      297_000_000, 2_997_000_000, "75", 150_000_000, ("2,65", 71_550_000), faktur_um=300_000_000),
             expect={"status": "DISPUTE", "codes": ["OVERBILLING"], "needs_cfo": True},
             actions=[{"do": "submit_cfo", "by": "dewi"}, {"do": "cfo_approve", "by": "hartono"}],
             final={"status": "POSTED", "net": 2_112_875_000}),
        dict(id="FR-03", hari="Selasa 13 Okt", persona="dewi", spv="SLO1", file="FR-03_BKM_kontrak-G_klaim-ganda.pdf",
             judul="Nomor invoice yang sama sudah ditagihkan ke SPV TRD2",
             doc=_doc("KORPORAT", "BKM", "SLO1", "INV/BKM/2026/077", "SPK/SLO/2026/007", d(2026, 10, 13),
                      "Infrastruktur Jalan Cluster Magnolia", "Termin 2", "35",
                      [("Pekerjaan jalan & saluran tahap 2 (20% s.d. 35%)", 450_000_000, "")],
                      49_500_000, 499_500_000, "35", 22_500_000, ("2,65", 11_925_000)),
             expect={"status": "HARD_STOP", "codes": ["KLAIM_GANDA"]},
             actions=[{"do": "cfo_reject", "by": "hartono", "reason": "Double billing dengan INV/BKM/2026/077 di TRD2"}],
             final={"status": "REJECTED"}),
        dict(id="FR-04", hari="Selasa 13 Okt", persona="dewi", spv="TRD2", file="FR-04_BJA_kontrak-C_termin-2_retensi-pph.pdf",
             judul="Retensi tidak dicantumkan, tarif PPh tidak sesuai SBU (tetap hijau, badge kuning)",
             doc=_doc("MENENGAH", "BJA", "TRD2", "BJA/INV/X/2026/042", "SPK/TRD/2026/003", d(2026, 10, 13),
                      "Pekerjaan Fondasi Tower B", "Termin 2", "30",
                      [("Pekerjaan bored pile Tower B", 250_000_000, "48 titik"),
                       ("Pekerjaan pile cap Tower B", 150_000_000, "12 unit")],
                      44_000_000, 444_000_000, "30", None, ("2,65", 10_600_000)),
             expect={"status": "READY", "codes": ["OMISI_RETENSI", "PAJAK_SBU"]},
             actions=[{"do": "post", "by": "dewi"}], final={"status": "POSTED", "net": 408_000_000}),
        dict(id="FR-05", hari="Selasa 13 Okt", persona="dewi", spv="TRD2", file="FR-05_AN_kontrak-E_salah-hitung.pdf",
             judul="Rincian pekerjaan tidak sama dengan total; ditolak",
             doc=_doc("MENENGAH", "AN", "TRD2", "AN/INV/2026/015", "SPK/TRD/2026/005", d(2026, 10, 13),
                      "Jasa Perencanaan Tower C", "Termin 2", "60",
                      [("Gambar kerja struktur Tower C", 100_000_000, "1 paket"),
                       ("Gambar kerja MEP Tower C", 50_000_000, "1 paket")],
                      17_600_000, 177_600_000, "60", 8_000_000, ("3,50", 5_600_000)),
             expect={"status": "DISPUTE", "codes": ["MATEMATIKA"]},
             actions=[{"do": "reject", "by": "dewi", "reason": R}], final={"status": "REJECTED"}),
        dict(id="FR-06", hari="Rabu 14 Okt", persona="dewi", spv="TRD2", file="FR-06_AN_kontrak-E_revisi.pdf",
             judul="Invoice revisi dari vendor, sekarang bersih",
             doc=_doc("MENENGAH", "AN", "TRD2", "AN/INV/2026/015-R", "SPK/TRD/2026/005", d(2026, 10, 14),
                      "Jasa Perencanaan Tower C", "Termin 2 (revisi)", "60",
                      [("Gambar kerja struktur Tower C", 100_000_000, "1 paket"),
                       ("Gambar kerja MEP Tower C", 60_000_000, "1 paket")],
                      17_600_000, 177_600_000, "60", 8_000_000, ("3,50", 5_600_000)),
             expect={"status": "READY", "codes": []},
             actions=[{"do": "post", "by": "dewi"}], final={"status": "POSTED", "net": 164_000_000}),
        dict(id="FR-07", hari="Rabu 14 Okt", persona="budi", spv="GCT3", file="FR-07_PP_kontrak-F_nominal-digelembungkan.pdf",
             judul="Progres jujur 70%, tetapi nominal tagihan digelembungkan",
             doc=_doc("MENENGAH", "PP", "GCT3", "PP/2026/027", "SPK/GCT/2026/006", d(2026, 10, 14),
                      "Jasa Pengawasan Konstruksi Garden City", "Termin 2", "70",
                      [("Jasa pengawasan konstruksi September-Oktober 2026", 150_000_000, "2 bulan")],
                      16_500_000, 166_500_000, "70", 7_500_000, ("6,00", 9_000_000)),
             expect={"status": "DISPUTE", "codes": ["NILAI_TIDAK_SESUAI_PROGRES", "FAKTUR_PAJAK"]},
             actions=[{"do": "post", "by": "budi"}], final={"status": "POSTED", "net": 120_000_000}),
        dict(id="FR-08", hari="Rabu 14 Okt", persona="budi", spv="GCT3", file="FR-08_IBP_kontrak-D_bersih_hasil-scan.pdf",
             judul="Dokumen hasil scan, bersih; ERP sempat gagal lalu dikirim ulang",
             doc=_doc("MENENGAH", "IBP", "GCT3", "IBP/INV/2026/019", "SPK/GCT/2026/004", d(2026, 10, 14),
                      "Design & Build Clubhouse Garden City", "Termin 2", "45",
                      [("Design & build clubhouse tahap 2 (30% s.d. 45%)", 330_000_000, "15%"),
                       ("Potongan pengembalian uang muka 10%", -33_000_000, "")],
                      32_670_000, 329_670_000, "45", 16_500_000, ("2,65", 7_870_500), faktur_um=33_000_000, scan=True),
             expect={"status": "READY", "codes": []},
             actions=[{"do": "erp_fail", "on": True}, {"do": "post", "by": "budi", "expect": "ERP_GAGAL"},
                      {"do": "erp_fail", "on": False}, {"do": "resend", "by": "budi"}],
             final={"status": "POSTED", "net": 305_299_500}),
        dict(id="FR-09", hari="Kamis 15 Okt", persona="dewi", spv="SLO1", file="FR-09_SK_kontrak-B_termin-4.pdf",
             judul="Termin berikutnya: progres sebelumnya otomatis 55% (dari FR-01)",
             doc=_doc("CV", "SK", "SLO1", "INV/SK/2026/036", "SPK/SLO/2026/002", d(2026, 10, 15), "Struktur Cluster C1",
                      "Termin 4", "75", [("Pekerjaan dinding & plester Cluster C1", 200_000_000, ""),
                                         ("Pekerjaan kusen & pintu Cluster C1", 100_000_000, "")],
                      33_000_000, 333_000_000, "75", 15_000_000, ("1,75", 5_250_000)),
             expect={"status": "READY", "codes": []},
             actions=[{"do": "post", "by": "dewi"}], final={"status": "POSTED", "net": 312_750_000}),
        dict(id="FR-10", hari="Kamis 15 Okt", persona="dewi", spv="TRD2", file="FR-10_BKM_kontrak-H_progres-inkremental.pdf",
             judul="Invoice menulis progres termin ini (7%), bukan kumulatif; auditor mengoreksi ke 37%",
             doc=_doc("KORPORAT", "BKM", "TRD2", "INV/BKM/2026/095", "SPK/TRD/2026/008", d(2026, 10, 15),
                      "Pekerjaan Struktur Tower A", "Termin 3", "7",
                      [("Pekerjaan struktur Tower A lantai 9-10", 350_000_000, "")],
                      38_500_000, 388_500_000, "37", 17_500_000, ("2,65", 9_275_000), inkremental=True),
             expect={"status": "DISPUTE", "codes_any": ["TERMIN_TIDAK_VALID"]},
             actions=[{"do": "override", "by": "dewi", "field": "progres_klaim", "value": "37",
                       "reason": "Invoice menulis progres termin (7%); kumulatif = 30% + 7% = 37%"},
                      {"do": "post", "by": "dewi"}],
             final={"status": "POSTED", "net": 361_725_000}),
        dict(id="FR-11", hari="Jumat 16 Okt", persona="dewi", spv="TRD2", file="FR-11_BJA_kontrak-C_nomor-kontrak-salah-tulis.pdf",
             judul="Vendor memakai nomor kontrak versinya sendiri; auditor menghubungkan manual",
             doc=_doc("MENENGAH", "BJA", "TRD2", "BJA/INV/X/2026/047", "SPK-TRD-03/2026", d(2026, 10, 16),
                      "Pekerjaan Fondasi Tower B", "Termin 3", "40",
                      [("Pekerjaan pile cap & tie beam Tower B", 400_000_000, "1 ls")],
                      44_000_000, 444_000_000, "40", 20_000_000, ("4,00", 16_000_000)),
             expect={"status": "DISPUTE", "codes": ["KONTRAK_TIDAK_DITEMUKAN"]},
             actions=[{"do": "set_contract", "by": "dewi", "contract": "SPK/TRD/2026/003",
                       "reason": "SPK-TRD-03/2026 adalah penomoran internal vendor untuk SPK/TRD/2026/003"},
                      {"do": "post", "by": "dewi"}],
             final={"status": "POSTED", "net": 408_000_000}),
        dict(id="FR-12", hari="Jumat 16 Okt", persona="dewi", spv="SLO1", file="FR-12_BKM_kontrak-A_denda-menelan-termin.pdf",
             judul="Proyek telat 16 hari: denda memotong habis termin kecil, sisanya terbawa",
             doc=_doc("KORPORAT", "BKM", "SLO1", "INV/BKM/2026/101", "SPK/SLO/2026/001", d(2026, 10, 16),
                      "Pembangunan Cluster Magnolia (120 unit)", "Termin 4", "76",
                      [("Progres pekerjaan finishing (75% s.d. 76%)", 100_000_000, ""),
                       ("Potongan pengembalian uang muka 10%", -10_000_000, "")],
                      9_900_000, 99_900_000, "76", 5_000_000, ("2,65", 2_385_000), faktur_um=10_000_000),
             expect={"status": "READY", "codes": []},
             actions=[{"do": "post", "by": "dewi"}],
             final={"status": "POSTED", "net": 0, "pen": 92_515_000, "pen_left": 27_485_000}),
    ]


# ---------- AR ----------

def _oldest(s, u: Unit, n=1) -> int:
    insts = s.exec(select(Installment).where(Installment.unit_id == u.id, Installment.paid < Installment.amount)
                   .order_by(Installment.seq)).all()
    return sum(i.amount - i.paid for i in insts[:n])


def ar_steps(s, units: dict[str, list[Unit]], demo_dir: Path) -> list[dict]:
    rnd = random.Random(23)
    ref = lambda: f"FT{rnd.randint(10**9, 10**10 - 1)}"  # noqa: E731
    slo, trd, gct = units["SLO1"], units["TRD2"], units["GCT3"]
    day = "2026-10-17"

    def row(u, memo, amount, sender=None, va="", bank="BCA"):
        return [day, sender or u.buyer.upper(), bank, amount, memo, ref(), va]

    half = (_oldest(s, trd[4]) // 2 // 100_000) * 100_000
    trd_rows = [
        row(trd[2], "TWR A 10/03 ANGS OKT", _oldest(s, trd[2])),
        row(trd[4], "CICILAN A-11-01 SEBAGIAN", half, bank="BNI"),
        row(trd[6], "UNIT A 11 03", _oldest(s, trd[6]) + 5_000_000, bank="MANDIRI"),
        row(trd[8], "VA PAYMENT", _oldest(s, trd[8]), va=trd[8].va),
        row(trd[10], "TRF A-12-03", _oldest(s, trd[10]), sender="IBU PURWANTI"),
        row(trd[11], "PELUNASAN 2 BLN A/12/04", _oldest(s, trd[11], 2), bank="BRI"),
        row(trd[7], "ANGS A-11-04", _oldest(s, trd[7]) - 200_000),
        [day, "PT ASURANSI SEJAHTERA", "MANDIRI", 4_250_000, "REFUND KLAIM 8812", ref(), ""],
    ]
    gct_rows = [
        row(gct[1], "BLOK G1 NO 2 KPR", _oldest(s, gct[1])),
        row(gct[3], "VA PAYMENT", _oldest(s, gct[3]), va=gct[3].va),
        row(gct[5], "G1/06 TRF", _oldest(s, gct[5]) - 150_000, bank="BNI"),
        row(gct[6], f"CICILAN G1-07 {gct[6].buyer.split()[0].upper()}", _oldest(s, gct[6])),
        row(gct[8], "ANGS OKT NOV G1-09", _oldest(s, gct[8], 2), bank="MANDIRI"),
        row(gct[10], "PEMBAYARAN UNIT G1 11", _oldest(s, gct[10])),
        row(gct[12], "TRF G1-13", _oldest(s, gct[12]), bank="BRI"),
        [day, "TOKO BANGUNAN MAJU", "BCA", 5_000_000, "TRANSFER DANA", ref(), ""],
    ]
    head = ["tanggal", "nama_pengirim", "bank", "nominal", "berita", "referensi", "no_va"]
    for name, rows in [("FR-14_rekening_koran_TRD2_2026-10-17.csv", trd_rows), ("FR-15_rekening_koran_GCT3_2026-10-17.csv", gct_rows)]:
        with open(demo_dir / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(head)
            w.writerows(rows)
    shutil.copyfile(demo_dir.parent / "rekening_koran_SLO1_2026-10-17.csv", demo_dir / "FR-13_rekening_koran_SLO1_2026-10-17.csv")
    sut = "TRF BPK SUTRISNO BLK C1/02"
    return [
        dict(id="FR-13", hari="Sabtu 17 Okt", persona="andi", spv="SLO1", file="FR-13_rekening_koran_SLO1_2026-10-17.csv",
             judul="Rekening koran SLO1: VA otomatis, waiver KPR, unit kembar milik satu investor",
             expect={"rows": 29, "auto": 6, "recommended": 19, "manual": 4, "duplicates": 1},
             decisions=[
                 {"memo": sut, "status": "RECOMMENDED", "unit": "C1-02",
                  "waiver": ["Pencairan KPR Bank", "Menunggu pencairan KPR Bank BTN"], "penalty": "WAIVED"},
                 {"memo": "TRF HENDRA GUNAWAN CLUSTER C1", "status": "MANUAL_REVIEW", "unit": "C1-03",
                  "note": "Dua unit milik pembeli yang sama; Andi memilih C1-03 sesuai konfirmasi telepon"},
                 {"memo": "PEMBAYARAN UNIT C1 08", "status": "RECOMMENDED", "unit": "C1-08"},
             ]),
        dict(id="FR-14", hari="Sabtu 17 Okt", persona="andi", spv="TRD2", file="FR-14_rekening_koran_TRD2_2026-10-17.csv",
             judul="Rekening koran TRD2: waiver eksekutif, bayar sebagian, lebih bayar, pengirim pasangan",
             expect={"rows": 8, "auto": 0, "recommended": 6, "manual": 2, "duplicates": 0},
             decisions=[
                 {"memo": "TWR A 10/03 ANGS OKT", "status": "RECOMMENDED", "unit": trd[2].code,
                  "waiver": ["Kewenangan Eksekutif", "Pembeli VIP, pemilik 3 unit di Tower A"], "penalty": "MENUNGGU_CFO",
                  "cfo": {"by": "hartono", "approve": True, "penalty": "WAIVED"}},
                 {"memo": "CICILAN A-11-01 SEBAGIAN", "status": "RECOMMENDED", "unit": trd[4].code, "settled": False},
                 {"memo": "UNIT A 11 03", "status": "RECOMMENDED", "unit": trd[6].code},
                 {"memo": "TRF A-12-03", "status": "MANUAL_REVIEW", "unit": trd[10].code,
                  "note": "Dikirim oleh pasangan pembeli; skor nama rendah, kode unit cocok"},
                 {"memo": "PELUNASAN 2 BLN A/12/04", "status": "RECOMMENDED", "unit": trd[11].code},
                 {"memo": "ANGS A-11-04", "status": "RECOMMENDED", "unit": trd[7].code, "selisih": 200_000},
             ]),
        dict(id="FR-15", hari="Sabtu 17 Okt", persona="sari", spv="GCT3", file="FR-15_rekening_koran_GCT3_2026-10-17.csv",
             judul="Rekening koran GCT3: waiver KPR, VA telat, potongan biaya transfer, dua angsuran",
             expect={"rows": 8, "auto": 0, "recommended": 7, "manual": 1, "duplicates": 0},
             decisions=[
                 {"memo": "BLOK G1 NO 2 KPR", "status": "RECOMMENDED", "unit": gct[1].code,
                  "waiver": ["Pencairan KPR Bank", "KPR Bank Mandiri cair 20 Oktober"], "penalty": "WAIVED"},
                 {"memo": "VA PAYMENT", "status": "RECOMMENDED", "unit": gct[3].code, "penalty": "DITAGIH"},
                 {"memo": "G1/06 TRF", "status": "RECOMMENDED", "unit": gct[5].code, "selisih": 150_000},
                 {"memo": "ANGS OKT NOV G1-09", "status": "RECOMMENDED", "unit": gct[8].code},
             ]),
    ]


# ---------- tulis paket ----------

def _rp(n):
    return "Rp" + f"{n:,}".replace(",", ".")


ACT = {
    "post": "Setujui & posting ke ERP", "submit_cfo": "Ajukan ke CFO", "cfo_approve": "CFO: Setujui & posting ke ERP",
    "cfo_reject": "CFO: Tolak tagihan", "reject": "Tolak tagihan", "resend": "Kirim ulang ke ERP",
    "override": "Ubah nilai", "set_contract": "Pilih kontrak",
}
WHO = {"dewi": "Dewi (AP)", "budi": "Budi (AP)", "andi": "Andi (AR)", "sari": "Sari (AR)", "hartono": "Hartono (CFO)"}


def _act_text(a: dict) -> str:
    if a["do"] == "erp_fail":
        return ("Nyalakan" if a["on"] else "Matikan") + " **Simulasi ERP gagal** (klik chip mode di kanan atas)"
    t = f"{WHO[a['by']]}: **{ACT[a['do']]}**"
    if a["do"] == "override":
        t += f" field *{a['field']}* menjadi `{a['value']}`"
    if a["do"] == "set_contract":
        t += f" `{a['contract']}`"
    if a.get("reason"):
        t += f", alasan: “{a['reason']}”"
    if a.get("expect"):
        t += f" (hasil: {a['expect']})"
    return t


def write_guide(out: Path, ap: list[dict], ar: list[dict]):
    L = ["# Skenario full run OmniAudit AI", "",
         "Satu minggu kerja fiktif (12–17 Oktober 2026) di tiga SPV. Semua nama, NPWP, dan rekening fiktif.", "",
         "**Persiapan:** hentikan server, lalu dari folder `backend` jalankan `uv run python -m app.seed --full-run` "
         "(data master tanpa tagihan contoh), nyalakan server lagi, dan buka http://localhost:8000.", "",
         "**Otomatis:** `uv run python scripts/full_run.py` menjalankan semua langkah ini dan mencocokkan hasilnya "
         "(tambahkan `--live` untuk menjalankannya ke database server agar hasilnya terlihat di aplikasi).", "",
         "Urutan penting: termin berikutnya pada kontrak yang sama baru bisa diaudit setelah termin sebelumnya "
         "diposting (FR-09 setelah FR-01, FR-11 setelah FR-04, FR-12 setelah FR-02, FR-06 setelah FR-05 ditolak).", "",
         "## Tagihan kontraktor (AP)", "",
         "| Langkah | Hari | Masuk sebagai / SPV | File | Yang diuji | Hasil setelah unggah | Aksi | Hasil akhir |",
         "|---|---|---|---|---|---|---|---|"]
    for st in ap:
        e, f = st["expect"], st["final"]
        codes = ", ".join(e.get("codes") or e.get("codes_any") or []) or "tanpa temuan"
        res = f"{e['status']} ({codes})" + (", butuh CFO" if e.get("needs_cfo") else "")
        fin = f["status"] + (f", Net Payable {_rp(f['net'])}" if "net" in f else "")
        if "pen" in f:
            fin += f", denda dipotong {_rp(f['pen'])}, sisa {_rp(f['pen_left'])} terbawa"
        acts = "<br>".join(_act_text(a) for a in st["actions"])
        L.append(f"| {st['id']} | {st['hari']} | {WHO[st['persona']]} / {st['spv']} | `{st['file']}` | {st['judul']} | "
                 f"{res} | {acts} | {fin} |")
    L += ["", "## Penerimaan pembeli (AR)", ""]
    for st in ar:
        e = st["expect"]
        L += [f"### {st['id']} ({st['hari']}): {WHO[st['persona']]}, {st['spv']}", "", st["judul"], "",
              f"Unggah `{st['file']}`. Ringkasan yang diharapkan: {e['rows']} baris, {e['auto']} otomatis via VA, "
              f"{e['recommended']} siap dikonfirmasi, {e['manual']} tinjau manual, {e['duplicates']} kemungkinan duplikat.", "",
              "| Berita transfer | Status awal | Keputusan | Hasil |", "|---|---|---|---|"]
        for d in st["decisions"]:
            dec = f"Pilih unit {d['unit']}" if d["status"] == "MANUAL_REVIEW" else f"Konfirmasi unit {d['unit']}"
            if d.get("waiver"):
                dec += f" + waiver *{d['waiver'][0]}* (“{d['waiver'][1]}”)"
            res = "Teralokasi"
            if d.get("penalty"):
                res += f", denda {d['penalty'].replace('_', ' ').lower()}"
            if d.get("cfo"):
                res += f"; Hartono menyetujui waiver di Ruang CFO, denda {d['cfo']['penalty'].lower()}"
            if d.get("settled") is False:
                res += ", angsuran baru terbayar sebagian"
            if d.get("selisih"):
                res += f", selisih biaya transfer {_rp(d['selisih'])} dianggap lunas"
            if d.get("note"):
                res += f". {d['note']}"
            L.append(f"| `{d['memo']}` | {d['status']} | {dec} | {res} |")
        L.append("")
    L += ["## Setelah semua langkah", "",
          "- Ruang CFO: tidak ada lagi antrean; **Verifikasi integritas** menunjukkan rantai hash utuh.",
          "- Dasbor Semua SPV: kartu *Kebocoran dicegah* naik dari FR-01 dan FR-02.",
          "- Akurasi agen: field *progres klaim* tercatat satu koreksi (FR-10).", ""]
    (out / "SKENARIO.md").write_text("\n".join(L), encoding="utf-8")


def build(s, units: dict[str, list[Unit]], demo_dir: Path, scan: bool = True) -> Path:
    out = demo_dir / "full-run"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    ap = ap_steps()
    for st in ap:
        doc = st.pop("doc")
        doc.scan = doc.scan and scan
        build_doc(doc, out / st["file"])
    ar = ar_steps(s, units, out)
    (out / "skenario.json").write_text(json.dumps({"ap": ap, "ar": ar}, indent=1, ensure_ascii=False), encoding="utf-8")
    write_guide(out, ap, ar)
    return out
