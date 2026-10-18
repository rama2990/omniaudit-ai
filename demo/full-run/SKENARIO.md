# Skenario full run OmniAudit AI

Satu minggu kerja fiktif (12–17 Oktober 2026) di tiga SPV. Semua nama, NPWP, dan rekening fiktif.

**Persiapan:** hentikan server, lalu dari folder `backend` jalankan `uv run python -m app.seed --full-run` (data master tanpa tagihan contoh), nyalakan server lagi, dan buka http://localhost:8000.

**Otomatis:** `uv run python scripts/full_run.py` menjalankan semua langkah ini dan mencocokkan hasilnya (tambahkan `--live` untuk menjalankannya ke database server agar hasilnya terlihat di aplikasi).

Urutan penting: termin berikutnya pada kontrak yang sama baru bisa diaudit setelah termin sebelumnya diposting (FR-09 setelah FR-01, FR-11 setelah FR-04, FR-12 setelah FR-02, FR-06 setelah FR-05 ditolak).

## Tagihan kontraktor (AP)

| Langkah | Hari | Masuk sebagai / SPV | File | Yang diuji | Hasil setelah unggah | Aksi | Hasil akhir |
|---|---|---|---|---|---|---|---|
| FR-01 | Senin 12 Okt | Dewi (AP) / SLO1 | `FR-01_SK_kontrak-B_termin-3_overbilling.pdf` | Overbilling: invoice 60%, BAP fisik 55% | DISPUTE (OVERBILLING) | Dewi (AP): **Setujui & posting ke ERP** | POSTED, Net Payable Rp234.562.500 |
| FR-02 | Senin 12 Okt | Dewi (AP) / SLO1 | `FR-02_BKM_kontrak-A_termin-3_butuh-CFO.pdf` | Klaim Rp2,997 M melebihi BAP; wajib persetujuan CFO | DISPUTE (OVERBILLING), butuh CFO | Dewi (AP): **Ajukan ke CFO**<br>Hartono (CFO): **CFO: Setujui & posting ke ERP** | POSTED, Net Payable Rp2.112.875.000 |
| FR-03 | Selasa 13 Okt | Dewi (AP) / SLO1 | `FR-03_BKM_kontrak-G_klaim-ganda.pdf` | Nomor invoice yang sama sudah ditagihkan ke SPV TRD2 | HARD_STOP (KLAIM_GANDA) | Hartono (CFO): **CFO: Tolak tagihan**, alasan: “Double billing with INV/BKM/2026/077 in TRD2” | REJECTED |
| FR-04 | Selasa 13 Okt | Dewi (AP) / TRD2 | `FR-04_BJA_kontrak-C_termin-2_retensi-pph.pdf` | Retensi tidak dicantumkan, tarif PPh tidak sesuai SBU (tetap hijau, badge kuning) | READY (OMISI_RETENSI, PAJAK_SBU) | Dewi (AP): **Setujui & posting ke ERP** | POSTED, Net Payable Rp408.000.000 |
| FR-05 | Selasa 13 Okt | Dewi (AP) / TRD2 | `FR-05_AN_kontrak-E_salah-hitung.pdf` | Rincian pekerjaan tidak sama dengan total; ditolak | DISPUTE (MATEMATIKA) | Dewi (AP): **Tolak tagihan**, alasan: “Line items do not add up to the total; vendor asked to revise the invoice.” | REJECTED |
| FR-06 | Rabu 14 Okt | Dewi (AP) / TRD2 | `FR-06_AN_kontrak-E_revisi.pdf` | Invoice revisi dari vendor, sekarang bersih | READY (tanpa temuan) | Dewi (AP): **Setujui & posting ke ERP** | POSTED, Net Payable Rp164.000.000 |
| FR-07 | Rabu 14 Okt | Budi (AP) / GCT3 | `FR-07_PP_kontrak-F_nominal-digelembungkan.pdf` | Progres jujur 70%, tetapi nominal tagihan digelembungkan | DISPUTE (NILAI_TIDAK_SESUAI_PROGRES, FAKTUR_PAJAK) | Budi (AP): **Setujui & posting ke ERP** | POSTED, Net Payable Rp120.000.000 |
| FR-08 | Rabu 14 Okt | Budi (AP) / GCT3 | `FR-08_IBP_kontrak-D_bersih_hasil-scan.pdf` | Dokumen hasil scan, bersih; ERP sempat gagal lalu dikirim ulang | READY (tanpa temuan) | Nyalakan **Simulasi ERP gagal** (klik chip mode di kanan atas)<br>Budi (AP): **Setujui & posting ke ERP** (hasil: ERP_GAGAL)<br>Matikan **Simulasi ERP gagal** (klik chip mode di kanan atas)<br>Budi (AP): **Kirim ulang ke ERP** | POSTED, Net Payable Rp305.299.500 |
| FR-09 | Kamis 15 Okt | Dewi (AP) / SLO1 | `FR-09_SK_kontrak-B_termin-4.pdf` | Termin berikutnya: progres sebelumnya otomatis 55% (dari FR-01) | READY (tanpa temuan) | Dewi (AP): **Setujui & posting ke ERP** | POSTED, Net Payable Rp312.750.000 |
| FR-10 | Kamis 15 Okt | Dewi (AP) / TRD2 | `FR-10_BKM_kontrak-H_progres-inkremental.pdf` | Invoice menulis progres termin ini (7%), bukan kumulatif; auditor mengoreksi ke 37% | DISPUTE (TERMIN_TIDAK_VALID) | Dewi (AP): **Ubah nilai** field *progres_klaim* menjadi `37`, alasan: “Invoice states this period only (7%); cumulative = 30% + 7% = 37%”<br>Dewi (AP): **Setujui & posting ke ERP** | POSTED, Net Payable Rp361.725.000 |
| FR-11 | Jumat 16 Okt | Dewi (AP) / TRD2 | `FR-11_BJA_kontrak-C_nomor-kontrak-salah-tulis.pdf` | Vendor memakai nomor kontrak versinya sendiri; auditor menghubungkan manual | DISPUTE (KONTRAK_TIDAK_DITEMUKAN) | Dewi (AP): **Pilih kontrak** `SPK/TRD/2026/003`, alasan: “SPK-TRD-03/2026 is the vendor numbering for SPK/TRD/2026/003”<br>Dewi (AP): **Setujui & posting ke ERP** | POSTED, Net Payable Rp408.000.000 |
| FR-12 | Jumat 16 Okt | Dewi (AP) / SLO1 | `FR-12_BKM_kontrak-A_denda-menelan-termin.pdf` | Proyek telat 16 hari: denda memotong habis termin kecil, sisanya terbawa | READY (tanpa temuan) | Dewi (AP): **Setujui & posting ke ERP** | POSTED, Net Payable Rp0, denda dipotong Rp92.515.000, sisa Rp27.485.000 terbawa |

## Penerimaan pembeli (AR)

### FR-13 (Sabtu 17 Okt): Andi (AR), SLO1

Rekening koran SLO1: VA otomatis, waiver KPR, unit kembar milik satu investor

Unggah `FR-13_rekening_koran_SLO1_2026-10-17.csv`. Ringkasan yang diharapkan: 29 baris, 6 otomatis via VA, 19 siap dikonfirmasi, 4 tinjau manual, 1 kemungkinan duplikat.

| Berita transfer | Status awal | Keputusan | Hasil |
|---|---|---|---|
| `TRF BPK SUTRISNO BLK C1/02` | RECOMMENDED | Konfirmasi unit C1-02 + waiver *Mortgage disbursement* (“Waiting for BTN mortgage disbursement”) | Teralokasi, denda waived |
| `TRF HENDRA GUNAWAN CLUSTER C1` | MANUAL_REVIEW | Pilih unit C1-03 | Teralokasi. Dua unit milik pembeli yang sama; Andi memilih C1-03 sesuai konfirmasi telepon |
| `PEMBAYARAN UNIT C1 08` | RECOMMENDED | Konfirmasi unit C1-08 | Teralokasi |

### FR-14 (Sabtu 17 Okt): Andi (AR), TRD2

Rekening koran TRD2: waiver eksekutif, bayar sebagian, lebih bayar, pengirim pasangan

Unggah `FR-14_rekening_koran_TRD2_2026-10-17.csv`. Ringkasan yang diharapkan: 8 baris, 0 otomatis via VA, 6 siap dikonfirmasi, 2 tinjau manual, 0 kemungkinan duplikat.

| Berita transfer | Status awal | Keputusan | Hasil |
|---|---|---|---|
| `TWR A 10/03 ANGS OKT` | RECOMMENDED | Konfirmasi unit A-10-03 + waiver *Executive authority* (“VIP buyer, owns 3 units in Tower A”) | Teralokasi, denda menunggu cfo; Hartono menyetujui waiver di Ruang CFO, denda waived |
| `CICILAN A-11-01 SEBAGIAN` | RECOMMENDED | Konfirmasi unit A-11-01 | Teralokasi, angsuran baru terbayar sebagian |
| `UNIT A 11 03` | RECOMMENDED | Konfirmasi unit A-11-03 | Teralokasi |
| `TRF A-12-03` | MANUAL_REVIEW | Pilih unit A-12-03 | Teralokasi. Dikirim oleh pasangan pembeli; skor nama rendah, kode unit cocok |
| `PELUNASAN 2 BLN A/12/04` | RECOMMENDED | Konfirmasi unit A-12-04 | Teralokasi |
| `ANGS A-11-04` | RECOMMENDED | Konfirmasi unit A-11-04 | Teralokasi, selisih biaya transfer Rp200.000 dianggap lunas |

### FR-15 (Sabtu 17 Okt): Sari (AR), GCT3

Rekening koran GCT3: waiver KPR, VA telat, potongan biaya transfer, dua angsuran

Unggah `FR-15_rekening_koran_GCT3_2026-10-17.csv`. Ringkasan yang diharapkan: 8 baris, 0 otomatis via VA, 7 siap dikonfirmasi, 1 tinjau manual, 0 kemungkinan duplikat.

| Berita transfer | Status awal | Keputusan | Hasil |
|---|---|---|---|
| `BLOK G1 NO 2 KPR` | RECOMMENDED | Konfirmasi unit G1-02 + waiver *Mortgage disbursement* (“Mandiri mortgage disburses on 20 October”) | Teralokasi, denda waived |
| `VA PAYMENT` | RECOMMENDED | Konfirmasi unit G1-04 | Teralokasi, denda ditagih |
| `G1/06 TRF` | RECOMMENDED | Konfirmasi unit G1-06 | Teralokasi, selisih biaya transfer Rp150.000 dianggap lunas |
| `ANGS OKT NOV G1-09` | RECOMMENDED | Konfirmasi unit G1-09 | Teralokasi |

## Setelah semua langkah

- Ruang CFO: tidak ada lagi antrean; **Verifikasi integritas** menunjukkan rantai hash utuh.
- Dasbor Semua SPV: kartu *Kebocoran dicegah* naik dari FR-01 dan FR-02.
- Akurasi agen: field *progres klaim* tercatat satu koreksi (FR-10).
