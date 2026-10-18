---
title: OmniAudit AI
status: final
created: 2026-10-18
updated: 2026-10-18
supersedes: "PRD Hckthon.txt v2.0-FINAL"
---

# PRD: OmniAudit AI — Audit & Rekonsiliasi Otomatis Dual-Engine untuk Developer Properti

**Versi:** 3.1 (final hackathon) · **Pemangku kepentingan:** Finance AP, Sales Admin & Collection AR, CFO

## 0. Tujuan Dokumen

PRD ini merapikan PRD v2.0 (`D:\Project\Hackathon\PRD Hckthon.txt`) menjadi dasar yang bisa langsung dibangun dalam satu minggu untuk demo hackathon. Perubahan utama dari v2.0:

- **Rumus termin ditulis ulang supaya benar secara pajak.** PPN tidak lagi terhitung dua kali. Pajak atas porsi uang muka tidak dikenakan ulang. Jurnal selalu berimbang.
- **Semua aturan yang sebelumnya kabur diberi angka pasti.**
- **Siklus status AP dan AR didefinisikan.**
- **Semua integrasi eksternal disimulasikan (mock).**

Istilah di §3 Glosarium wajib dipakai apa adanya. FR dinomori secara global dan diberi prioritas **[M]** Must, **[S]** Should, atau **[C]** Could. Asumsi ditandai `[ASSUMPTION]` dan dikumpulkan di §10. Keputusan teknis ada di `addendum.md`, dan riwayat keputusan di `.memlog.md`.

## 1. Visi

Developer properti skala besar memproses ribuan tagihan kontraktor dan puluhan ribu pembayaran pembeli setiap bulan, tersebar di banyak entitas SPV. Verifikasinya masih manual, sehingga terjadi kebocoran: kontraktor menagih melebihi progres fisik, denda dan retensi lupa dipotong, dan dana pembeli menggantung tanpa identitas.

OmniAudit AI adalah dasbor audit dengan pola **Human-in-the-Loop**. AI (Gemini) membaca dokumen dan mengenali angka-angkanya. Seluruh perhitungan uang dan aturan audit dijalankan oleh kode deterministik, sehingga hasilnya selalu bisa ditelusuri dan diulang. Transaksi yang bersih dan yakin disetujui dengan satu klik. Transaksi yang bermasalah dikunci, lalu dibuka di layar audit split-view supaya manusia bisa memutuskan dengan cepat. Semua keputusan tercatat di jejak audit yang tidak bisa diubah.

## 2. Pengguna

### 2.1 Jobs To Be Done

- **Finance AP Lead:** "Pastikan setiap rupiah yang dibayar ke kontraktor sesuai progres fisik dan kontrak, tanpa harus mengecek manual selama 3–5 hari."
- **Sales Admin & Collection Lead:** "Temukan pembayaran ini milik unit siapa, hitung dendanya, dan kabari pembeli pada hari yang sama."
- **CFO:** "Lihat di mana uang bocor di seluruh SPV, dan putuskan sendiri kasus yang nilainya besar."

### 2.2 Peran & Hak Akses

| Peran | Lingkup SPV | Hak utama |
|---|---|---|
| `ROLE_FIN_AP` | SPV yang ditugaskan saja | Unggah dokumen AP, tinjau kalkulasi, Override dengan alasan, posting Termin yang tidak butuh CFO, Reject Termin (kecuali Hard Stop) |
| `ROLE_SALES_AR` | SPV yang ditugaskan saja | Unggah rekening koran, konfirmasi alokasi, Waiver (kecuali alasan Kewenangan Eksekutif), notifikasi pembeli |
| `ROLE_CFO_EXEC` | Semua SPV | Dasbor eksekutif, keputusan atas Termin Menunggu CFO, membuka/menolak Hard Stop, Waiver Kewenangan Eksekutif, Jejak Audit & akurasi AI |

### 2.3 Perjalanan Pengguna Utama

*Diturunkan dari Bab 3 PRD v2.0. Angka-angkanya diambil dari contoh acuan di FR-14, sehingga skrip demo bisa diulang persis.*

- **UJ-1. Dewi menemukan overbilling sebelum uangnya keluar.**
  Dewi (AP Lead, PT Suburban Land One) memilih persona "Dewi – AP" di role switch, lalu mengunggah satu PDF Termin Kontrak B berisi invoice, BAP, faktur pajak, dan foto progres. Konsol Telemetry menampilkan Parser Agent, lalu Contract Agent, lalu Adversarial Auditor bekerja. Invoice mengklaim progres 60%, sedangkan BAP fisik hanya 55%. Termin terkunci sebagai **Dispute**. Dewi membuka split-view: di kiri, PDF dengan kotak sorotan pada angka "60%" dan "55%"; di kanan, tabel Klaim Invoice (Net Payable Rp312.750.000) vs Terverifikasi BAP (Rp234.562.500). Ia menerima koreksi sistem dan menekan **Approve & Post to ERP**. Muncul ERP Batch Reference ID.
  **Edge case:** pada Kontrak A, Bruto Tagihan klaim mencapai Rp2.997.000.000 (> Rp500 jt). Tombol posting berubah menjadi **Ajukan ke CFO** (lihat UJ-3).
- **UJ-2. Andi membereskan penerimaan menggantung pagi ini.**
  Andi (Sales Admin) mengunggah CSV rekening koran VA. Penerimaan yang cocok persis lewat nomor VA langsung teralokasi. Sisanya masuk ke antrean Penerimaan Unallocated. Satu baris berbunyi "TRF BPK SUTRISNO BLK C1/02". Kartu rekomendasi menunjukkan Unit C1-02 atas nama Sutrisno Wibowo dengan status RECOMMENDED MATCH. Pembayaran telat 12 hari, sehingga grid denda menampilkan Denda Angsuran. Pembeli sedang menunggu pencairan KPR, jadi Andi mencentang **Apply Penalty Waiver** dengan alasan *Pencairan KPR Bank*, lalu menekan **Confirm Allocation & Send Buyer Notification**. Kuitansi muncul di Outbox WhatsApp/email.
  **Edge case:** Match Score < 85%. Status menjadi Manual Review, dan Andi memilih Unit sendiri.
- **UJ-3. Pak Hartono memutuskan kasus besar dan melihat kebocoran.**
  CFO memilih "Semua SPV". Kartu metrik menunjukkan AR unallocated, AP pending, jumlah Dispute, kecepatan rekonsiliasi, dan **kebocoran yang dicegah**. Antrean CFO berisi Hard Stop untuk invoice yang sama di dua SPV. Ia membaca Jejak Audit, lalu menolaknya. Berikutnya ia membuka Termin Kontrak A yang diajukan Dewi (klaim Rp2.997.000.000; terverifikasi Net Payable Rp2.112.875.000), menyetujuinya, dan sistem langsung memposting ke ERP.

## 3. Glosarium

- **SPV** — Entitas PT terpisah per proyek. Setiap Kontrak, Termin, Unit, dan Penerimaan milik tepat satu SPV.
- **Vendor** — Kontraktor/konsultan, beserta NPWP (dinormalisasi ke 16 digit), Jenis Jasa (Pelaksanaan / Perencanaan / Pengawasan / Terintegrasi), dan Kualifikasi SBU (Kecil / Menengah / Besar / Tanpa SBU).
- **Kontrak** — Master perjanjian dengan Vendor. Berisi:
  - **DPP Kontrak** (nilai pekerjaan sebelum PPN; Nilai Kontrak termasuk PPN hanya untuk tampilan)
  - Tarif Retensi (default 5%)
  - Persen Uang Muka
  - Tanggal Target Selesai
  - Tarif Denda Harian (default 2‰)
  - Batas Denda (default 5%)
- **Paket Dokumen AP** — Satu unggahan PDF berisi Invoice, BAP, Faktur Pajak, dan Foto Progres.
- **BAP** — Berita Acara Pemeriksaan yang menyatakan **Progres BAP**, yaitu persen kumulatif fisik.
- **Termin** — Satu tagihan progres atas satu Kontrak. Maksimal satu Termin terbuka (belum Posted/Rejected) per Kontrak.
- **Progres Klaim** — Persen kumulatif yang ditagih di invoice. **Progres Disetujui** = min(Progres Klaim, Progres BAP). **Progres Sebelumnya** = Progres Disetujui pada Termin terakhir yang sudah Posted.
- **Nilai Progres Termin** — Nilai pekerjaan Termin ini sebelum PPN dan sebelum Potongan Uang Muka.
- **Uang Muka / Saldo Uang Muka / Potongan Uang Muka** — Uang muka kontrak. Saldo awalnya = Persen Uang Muka × DPP Kontrak. Saldo dikembalikan sedikit demi sedikit lewat Potongan Uang Muka di setiap Termin.
- **DPP Faktur** — Nilai Progres Termin − Potongan Uang Muka. Ini dasar PPN dan PPh Termin. *Catatan: istilah "DPP Nilai Lain 11/12" di faktur rezim PPN 12% hanya untuk tampilan faktur. Semua hitungan di PRD ini memakai nilai sebelum PPN.*
- **Bruto Tagihan** — DPP Faktur + PPN, yaitu nilai yang ditagih Vendor. **Bruto Tertulis** — Bruto yang tertulis di invoice.
- **Retensi** — Jaminan pemeliharaan yang ditahan sampai BAST II.
- **Denda Keterlambatan Kontraktor** — Denda karena tanggal BAP melewati Tanggal Target Selesai. **Denda Tertunggak** — denda yang sudah timbul tapi belum dipotong.
- **Net Payable** — Nilai yang benar-benar dibayar ke Vendor.
- **Skor Kepastian** — Keyakinan AI atas hasil ekstraksi Field Wajib satu Paket Dokumen AP (0–100%).
- **Anomali** — Temuan Adversarial Auditor dengan Tingkat Keparahan MEDIUM / HIGH / CRITICAL.
- **Jalur Hijau** (status `READY`), **Dispute**, **Hard Stop**, **Menunggu CFO** — status Termin, lihat FR-23.
- **Override** — Perubahan nilai oleh pengguna terhadap hasil sistem. Wajib disertai Alasan Override.
- **Batch Jurnal** — Kumpulan baris jurnal berimbang untuk satu transaksi, dikirim ke ERP dan dibalas dengan **ERP Batch Reference ID**.
- **Pembeli / Unit / PPJB / Angsuran** — Pembeli terikat pada Unit lewat PPJB yang berisi Jadwal Angsuran.
- **Penerimaan** — Satu baris mutasi kredit di rekening koran/VA. **Penerimaan Unallocated** adalah Penerimaan yang belum terhubung ke Unit.
- **Match Score** — Skor komposit kecocokan antara Penerimaan dan Unit (0–100%).
- **Denda Angsuran** — Denda Pembeli karena membayar Angsuran setelah tanggal jatuh tempo.
- **Waiver** — Penghapusan Denda Angsuran, disertai Alasan Waiver.
- **Titipan** — Kelebihan bayar Pembeli yang belum teralokasi ke Angsuran.
- **Outbox** — Daftar notifikasi WhatsApp/email mock yang "terkirim".
- **Jejak Audit** — Log tindakan yang hanya bisa ditambah (append-only) dan bisa dideteksi bila diubah (tamper-evident).
- **Telemetry** — Aliran langkah kerja agen yang ditampilkan langsung ke pengguna.

## 4. Fitur

### 4.1 Akses & Konteks SPV

**Deskripsi:** Pengganti SSO untuk demo. Pengguna memilih persona yang sudah memiliki peran dan daftar SPV, lalu memilih SPV aktif.

#### FR-1 [M]: Role switch
Pengguna dapat memilih persona demo, minimal satu per peran.
- Setiap persona punya tepat satu peran.
- Semua permintaan API membawa identitas persona.
- Aksi di luar hak peran ditolak dengan HTTP 403.

#### FR-2 [M]: SPV Selector & isolasi data
Pengguna dapat memilih SPV aktif dari SPV yang ditugaskan kepadanya. Hanya CFO yang mendapat opsi "Semua SPV".
- Pengguna AP/AR tidak dapat membaca atau mengubah data SPV lain lewat UI maupun API. Ini diverifikasi dengan tes API.
- FR-16 (Klaim Ganda) memeriksa lintas SPV di sisi server tanpa membuka data SPV lain ke pengguna AP. Pesan yang ditampilkan hanya "duplikat ditemukan di SPV lain".

### 4.2 Ingesti & Ekstraksi Dokumen AP

**Deskripsi:** OCR lokal mengambil teks beserta koordinatnya. Gemini mengklasifikasi tiap halaman dan memilih nilai setiap field dari kata-kata hasil OCR. Setiap nilai harus berlabuh (grounded) ke kata OCR asli supaya bisa disorot di PDF dan tidak bisa dikarang oleh AI. Mewujudkan UJ-1.

#### FR-3 [M]: Unggah Paket Dokumen AP
AP Lead dapat mengunggah PDF multi-halaman (≤ 30 halaman, ≤ 25 MB) untuk SPV aktif.
- File non-PDF atau yang melebihi batas ditolak dengan pesan yang jelas.
- Setiap unggahan menjadi satu Termin berstatus `PROCESSING`.

#### FR-4 [M]: OCR lokal dengan koordinat
Sistem mengekstrak setiap kata beserta halaman dan kotak koordinatnya, tanpa layanan OCR eksternal.
- PDF digital memakai lapisan teks asli. Halaman hasil scan memakai OCR lokal.
- Halaman yang tidak terbaca ditandai, dan field di halaman itu mendapat keyakinan 0.

#### FR-5 [M]: Klasifikasi halaman & ekstraksi field oleh Gemini
Parser Agent (Gemini) mengklasifikasi tiap halaman sebagai Invoice / BAP / Faktur Pajak / Foto Progres / Lain, lalu mengekstrak:
- **Field Wajib:** nomor invoice, NPWP Vendor, nomor kontrak, Progres Klaim (kumulatif), Progres BAP (kumulatif), tanggal BAP, Bruto Tertulis.
- **Field Opsional:** line item (nilai sebelum PPN), retensi yang tercantum di invoice, tarif/nilai PPh 4(2) yang tercantum di invoice, dan dari Faktur Pajak: NSFP, NPWP penjual, DPP, PPN.

Aturannya:
- Setiap field berisi nilai, keyakinan 0–1, dan referensi ke kata OCR asalnya.
- Nilai yang tidak ditemukan pada kata OCR yang dirujuk dipaksa ber-keyakinan 0.
- Field Opsional yang memang tidak ada di dokumen bernilai `null`. Itu sah dan memicu aturan di §4.4.
- Jika invoice menyebut progres per termin (inkremental), Gemini menandainya dan tidak mengisinya sebagai kumulatif.
- Gemini hanya membaca. Ia tidak pernah menghitung uang.

#### FR-6 [M]: Skor Kepastian
Skor Kepastian = keyakinan terendah di antara Field Wajib. `[ASSUMPTION]` Field Opsional tidak mempengaruhi skor ini.

#### FR-7 [M]: Contract Agent
Sistem mencocokkan nomor kontrak ke master Kontrak di SPV aktif dan memuat ketentuan Kontrak beserta data SBU Vendor.
- Jika kontrak tidak ditemukan, status menjadi Dispute dengan pesan "Kontrak tidak ditemukan". Kolom kalkulasi kosong dan posting dinonaktifkan sampai AP Lead memilih Kontrak secara manual dari daftar SPV.
- [C] Tombol "Buat Kontrak cepat" dari UI, supaya juri bisa memakai PDF mereka sendiri.

### 4.3 Mesin Kalkulasi AP

**Deskripsi:** Kode deterministik menghitung setiap Termin dua kali dengan rumus yang sama: sekali dengan P = Progres Klaim (kolom **Klaim Invoice**) dan sekali dengan P = Progres Disetujui (kolom **Terverifikasi BAP**). Aturan angka:
- Semua angka memakai desimal presisi, tidak memakai float.
- Setiap baris dibulatkan ke rupiah penuh (half-up).
- Baris turunan memakai nilai dasar yang sudah dibulatkan.
- Pembulatan e-Faktur/e-Bupot (ke bawah) tidak dimodelkan. `[ASSUMPTION]`

#### FR-8 [M]: Nilai Progres Termin
- Nilai Progres Termin = round(DPP Kontrak × P) − Σ Nilai Progres Termin yang sudah Posted pada Kontrak ini.
- Dihitung kumulatif supaya total semua Termin tepat sama dengan DPP Kontrak saat progres mencapai 100%.

#### FR-9 [M]: Potongan Uang Muka & DPP Faktur
- Potongan Uang Muka = min(round(Persen Uang Muka × Nilai Progres Termin), Saldo Uang Muka). Saat P = 100%, potongannya adalah seluruh sisa Saldo Uang Muka.
- DPP Faktur = Nilai Progres Termin − Potongan Uang Muka.
- Alasannya: PPN dan PPh atas uang muka sudah dikenakan saat uang muka dibayar, jadi tidak dikenakan lagi di Termin.

#### FR-10 [M]: PPN & Bruto Tagihan
- PPN = round(DPP Faktur × tarif PPN efektif). Tarif efektif disimpan sebagai konfigurasi, default 11% (= 12% × 11/12).
- Bruto Tagihan = DPP Faktur + PPN. Karena Bruto dihitung sebagai jumlah, jurnal selalu berimbang.

#### FR-11 [M]: PPh 4(2) berdasarkan SBU
Tarif diambil dari master Vendor, bukan dari dokumen. PPh = round(DPP Faktur × tarif).

| Jenis Jasa | Kecil | Menengah/Besar | Tanpa SBU |
|---|---|---|---|
| Pelaksanaan | 1,75% | 2,65% | 4,00% |
| Terintegrasi | 2,65% | 2,65% | 4,00% |
| Perencanaan / Pengawasan | 3,50% | 3,50% | 6,00% |

#### FR-12 [M]: Retensi
Retensi = round(Tarif Retensi × Nilai Progres Termin). Retensi tetap dipotong termasuk pada Termin 100%, karena baru dilepas di BAST II.

#### FR-13 [M]: Denda Keterlambatan Kontraktor
- Hari Terlambat = max(0, tanggal BAP − Tanggal Target Selesai).
- Denda Kumulatif = min(DPP Kontrak × Tarif Denda Harian × Hari Terlambat, DPP Kontrak × Batas Denda).
- Denda Tertunggak = Denda Kumulatif − Σ Potongan Denda yang sudah Posted.
- Potongan Denda = min(Denda Tertunggak, Bruto Tagihan − Retensi − PPh). Net Payable tidak pernah negatif.
- Sisa yang belum terpotong terbawa ke Termin berikutnya dan ditampilkan sebagai "Sisa denda belum terpotong Rp…".

#### FR-14 [M]: Net Payable & contoh acuan
**Net Payable = Bruto Tagihan − Retensi − Potongan Denda − PPh 4(2)**

**Contoh A (kasus CFO, UJ-3)** — wajib lolos sebagai tes otomatis, sama sampai ke rupiah:
- **Kontrak:** DPP Kontrak Rp10.000.000.000. Vendor Pelaksanaan, SBU Menengah. Uang Muka 10%; Saldo Uang Muka tersisa Rp500.000.000. Retensi 5%. Denda 2‰/hari, batas 5%. Target selesai 30-09-2026.
- **Termin:** Progres Sebelumnya 50%. Progres Klaim 80%, Progres BAP 75%. Tanggal BAP 10-10-2026, jadi terlambat 10 hari. Belum ada denda yang dipotong sebelumnya.

| Baris | Klaim Invoice (80%) | Terverifikasi BAP (75%) |
|---|---:|---:|
| Nilai Progres Termin | 3.000.000.000 | 2.500.000.000 |
| Potongan Uang Muka 10% | 300.000.000 | 250.000.000 |
| DPP Faktur | 2.700.000.000 | 2.250.000.000 |
| PPN 11% | 297.000.000 | 247.500.000 |
| **Bruto Tagihan** | **2.997.000.000** | **2.497.500.000** |
| Retensi 5% | 150.000.000 | 125.000.000 |
| Potongan Denda (10 hari) | 200.000.000 | 200.000.000 |
| PPh 4(2) 2,65% | 71.550.000 | 59.625.000 |
| **Net Payable** | **2.575.450.000** | **2.112.875.000** |

Jurnal kolom Terverifikasi:

| Sisi | Akun | Nilai |
|---|---|---:|
| Debit | Aset Real Estat – Bangunan dalam Penyelesaian | 2.500.000.000 |
| Debit | PPN Masukan | 247.500.000 |
| Kredit | Uang Muka Kontraktor | 250.000.000 |
| Kredit | Utang Retensi | 125.000.000 |
| Kredit | Pendapatan Lain-lain – Denda Kontraktor | 200.000.000 |
| Kredit | Utang PPh 4(2) | 59.625.000 |
| Kredit | Utang Usaha | 2.112.875.000 |

Total debit = total kredit = 2.747.500.000.

**Contoh B (alur langsung, UJ-1):**
- **Kontrak:** DPP Kontrak Rp1.500.000.000. Vendor Pelaksanaan, SBU Kecil. Tanpa Uang Muka. Retensi 5%. Tidak terlambat.
- **Termin:** Progres Sebelumnya 40%, Progres Klaim 60%, Progres BAP 55%.

| Baris | Klaim (60%) | Terverifikasi (55%) |
|---|---:|---:|
| Nilai Progres Termin = DPP Faktur | 300.000.000 | 225.000.000 |
| PPN 11% | 33.000.000 | 24.750.000 |
| Bruto Tagihan | 333.000.000 | 249.750.000 |
| Retensi 5% | 15.000.000 | 11.250.000 |
| PPh 4(2) 1,75% | 5.250.000 | 3.937.500 |
| **Net Payable** | **312.750.000** | **234.562.500** |

**Tes wajib tambahan:**
- Kasus angka tidak bulat: DPP Kontrak 7.345.678.901, progres 37,5% → 61,25%. Nilai acuannya dihitung manual saat implementasi.
- Tes properti: untuk input acak, total debit = total kredit dan Net Payable ≥ 0.
- Kasus denda melebihi termin: Kontrak A, termin 50% → 52%, terlambat 25 hari. Potongan Denda harus dibatasi dan sisanya terbawa.

### 4.4 Adversarial Auditor & Siklus Status AP

**Deskripsi:** Mesin aturan deterministik menguji setiap Termin dan menghasilkan daftar Anomali. Anomali menentukan status Termin. Mewujudkan UJ-1 dan UJ-3.

| FR | Anomali | Pemicu | Keparahan | Tindakan otomatis |
|---|---|---|---|---|
| FR-15 [M] | Overbilling Progres | Progres Klaim > Progres BAP | HIGH | Kalkulasi Terverifikasi memakai Progres BAP |
| FR-16 [M] | Klaim Ganda | Nomor invoice (huruf besar, tanpa spasi/tanda baca) + NPWP sama dengan Termin lain yang tidak berstatus Rejected | CRITICAL jika beda SPV (notifikasi ke CFO); HIGH jika SPV sama | — |
| FR-17 [M] | Omisi Retensi | Retensi tercantum di invoice `null` atau 0 | MEDIUM | Baris Retensi tetap dipotong (FR-12), badge kuning |
| FR-18 [M] | Ketidakcocokan Matematika | Σ line item + PPN tertulis ≠ Bruto Tertulis (toleransi Rp1) | HIGH | Tampilkan hitungan sistem vs nilai yang tertulis |
| FR-19 [M] | Nilai Tagihan Tidak Sesuai Progres | Bruto Tertulis ≠ Bruto Tagihan kolom Klaim (toleransi Rp1.000) | HIGH | Tampilkan selisihnya. Menangkap nominal yang digelembungkan walau progresnya benar. |
| FR-20 [M] | Pajak Tidak Sesuai SBU | PPh tercantum di invoice ≠ tarif master Vendor | MEDIUM | Pakai tarif master, badge kuning |
| FR-21 [S] | Faktur Pajak Tidak Sesuai | Faktur Pajak tidak ada, PPN faktur ≠ PPN hitungan (toleransi Rp1), atau NPWP penjual ≠ NPWP Vendor | MEDIUM | Badge kuning dan catatan "PPN Masukan belum dapat dikreditkan" |
| FR-22 [M] | Termin Tidak Valid | Progres Klaim ≤ Progres Sebelumnya (kemungkinan progres inkremental); progres > 100%; ada Termin terbuka lain pada Kontrak yang sama; atau P = 100% dan masih ada sisa Denda Tertunggak | HIGH | Pesan penyebab yang spesifik |

#### FR-23 [M]: Penentuan status & siklus Termin

Urutan prioritas: CRITICAL > HIGH atau Skor Kepastian < 85% > MEDIUM.

```
PROCESSING ──(gagal OCR/Gemini)──► GAGAL_PROSES ──(Proses ulang)──► PROCESSING
PROCESSING ──► HARD_STOP   jika ada CRITICAL
           ──► DISPUTE     jika ada HIGH atau Skor Kepastian < 85%
           ──► READY       selain itu (MEDIUM boleh, dengan badge kuning)

READY   ──(AP: Approve & Post)──────────────────────► POSTED / ERP_GAGAL
DISPUTE ──(AP: terima koreksi atau Override + alasan)
          ├─ butuh CFO? ──► MENUNGGU_CFO ──(CFO setuju: posting otomatis)──► POSTED / ERP_GAGAL
          │                              └─(CFO tolak)──► REJECTED
          └─ tidak ──────────────────────────────────► POSTED / ERP_GAGAL
HARD_STOP ──(CFO: buka)──► DISPUTE     ──(CFO: tolak)──► REJECTED
ERP_GAGAL ──(Kirim ulang)──► POSTED
READY / DISPUTE ──(AP: Reject + alasan)──► REJECTED
```

- **Butuh CFO** jika status Dispute dan max(Bruto Tertulis, Bruto Tagihan kolom Klaim) > Rp500.000.000.
- Status final adalah POSTED dan REJECTED. Termin Rejected tidak dihitung dalam FR-16.
- Sesaat sebelum posting, FR-8 sampai FR-14 dihitung ulang dari baseline terbaru. Jika hasilnya berubah, Termin kembali ke DISPUTE.

### 4.5 Layar Audit Split-View & Override (Layar 2)

**Deskripsi:** Layar dengan pembagian 50:50. Mewujudkan UJ-1.

#### FR-24 [M]: Panel kiri — penampil dokumen
- Menampilkan halaman PDF asli dengan navigasi per jenis dokumen.
- Setiap field yang diekstrak diberi kotak sorotan pada koordinat OCR-nya. Warna kotak: hijau = cocok, merah = terkait Anomali.
- Klik field di panel kanan membuat panel kiri melompat ke halaman dan kotak tersebut.

#### FR-25 [M]: Panel kanan — kontrak, komparasi, telemetry
- **Atas:** ringkasan Kontrak (Retensi, Saldo Uang Muka, Hari Terlambat, Denda Tertunggak, SBU, dan tarif PPh).
- **Tengah:** tabel Klaim Invoice vs Terverifikasi BAP dengan baris seperti FR-14, ditambah "Kebocoran dicegah" = selisih Net Payable kedua kolom.
- **Bawah:** konsol Telemetry yang menampilkan Parser Agent → Contract Agent → Adversarial Auditor → Mesin Kalkulasi secara live, serta daftar Anomali.

#### FR-26 [M]: Override & keputusan
AP Lead dapat menerima koreksi sistem, mengubah field hasil ekstraksi atau Progres Disetujui, atau me-Reject Termin.
- Override dan Reject wajib disertai alasan minimal 10 karakter.
- Progres Disetujui tidak boleh diisi di atas min(Progres Klaim, Progres BAP).
- Setiap Override memicu hitung ulang FR-8 sampai FR-23, lalu dicatat di Jejak Audit beserta nilai awal dan nilai baru.
- Tombol yang tersedia mengikuti FR-23: **Approve & Post to ERP**, **Ajukan ke CFO**, atau **Reject**.

### 4.6 Posting Jurnal ke ERP (mock)

#### FR-27 [M]: Susun Batch Jurnal
Sistem menyusun Batch Jurnal dengan akun seperti contoh FR-14. Baris bernilai 0 tidak ditulis. Batch yang tidak berimbang tidak bisa dikirim.

#### FR-28 [M]: Kirim ke ERP mock
Sistem mengirim Batch Jurnal ke endpoint ERP mock dan menerima ERP Batch Reference ID. Setelah itu sistem memperbarui Progres Sebelumnya, Saldo Uang Muka, dan Potongan Denda yang sudah Posted.
- Kegagalan ERP mock (bisa dipicu untuk demo) membuat status menjadi ERP_GAGAL tanpa ada data yang hilang.

### 4.7 Ingesti Rekening Koran AR

#### FR-29 [M]: Unggah CSV rekening koran
Sales Admin dapat mengunggah CSV dengan kolom: tanggal, nama pengirim, bank, nominal, berita transfer, nomor referensi bank (opsional), dan nomor VA (opsional).
- Penerimaan dengan nomor VA yang cocok persis ke Unit mendapat Match Score 100%.
  - Jika Angsuran tidak telat, Penerimaan langsung teralokasi lewat FR-36 dan notifikasi dikirim.
  - Jika telat, Penerimaan masuk antrean sebagai RECOMMENDED MATCH supaya keputusan Waiver tetap diambil manusia.
- Sisanya menjadi Penerimaan Unallocated.
- Baris yang sama persis (tanggal, nominal, berita, pengirim, dan referensi) dengan data yang sudah ada ditandai "kemungkinan duplikat". Baris itu tidak dibuang diam-diam.

#### FR-30 [C]: Webhook bank mock
Endpoint menerima satu Penerimaan dalam format JSON dan memprosesnya seperti satu baris CSV.

### 4.8 Pencocokan AR (Reconciliation Agent)

**Deskripsi:** Kode deterministik menilai setiap Penerimaan Unallocated terhadap semua Unit di SPV yang punya Angsuran belum lunas. Mewujudkan UJ-2.

#### FR-31 [M]: Match Score
**Match Score = 0,45 × S_unit + 0,35 × S_nama + 0,20 × S_nominal**

- **S_unit:** pola unit diambil dari berita transfer, lalu dinormalisasi:
  - huruf besar;
  - kata BLOK/BLK/TOWER/TWR/UNIT/NO dibuang;
  - pemisah `/ . spasi` diseragamkan menjadi `-`;
  - nol di depan setiap angka dibuang.

  Kode yang sama persis setelah normalisasi = 1,0. Jika semua bagian angka sama persis dan bagian huruf mirip (Jaro-Winkler ≥ 0,80), nilainya 0,7 `[ASSUMPTION]`. Selain itu 0. Bagian angka tidak pernah dicocokkan secara fuzzy.
- **S_nama:** nilai Jaro-Winkler tertinggi antara nama Pembeli di PPJB dan nama pengirim atau berita transfer, setelah gelar seperti BPK/BAPAK/IBU/SDR/H/HJ dibuang.
- **S_nominal:** nilai terbaik dari perbandingan nominal dengan Σ k Angsuran tertua yang belum lunas (k = 1..6), dengan atau tanpa Denda Angsuran berjalan.
  - Selisih ≤ Rp250.000 = 1,0.
  - Di atas itu = max(0, 1 − (selisih − 250.000) ÷ nilai pembanding). `[ASSUMPTION]`
- **Status:**
  - **RECOMMENDED MATCH** jika kandidat teratas ≥ 85% dan unggul ≥ 10 poin dari kandidat kedua.
  - **MANUAL REVIEW** selain itu.
- **Tes wajib:**
  - "BLOK C1/02", "C1-02", dan "C1-2" semuanya menjadi `C1-2`, sehingga S_unit = 1,0.
  - "C1-03" vs "C1-02" menghasilkan S_unit = 0.
  - Satu transfer untuk 2 Angsuran sekaligus menghasilkan S_nominal = 1,0.

#### FR-32 [M]: Kartu rekomendasi
Untuk setiap Penerimaan, sistem menampilkan 3 kandidat Unit teratas beserta nama di PPJB, Angsuran yang dicocokkan, rincian ketiga sub-skor, dan Match Score.

#### FR-33 [M]: Pilih manual
Pada status Manual Review, Sales Admin dapat mencari dan memilih Unit sendiri.

### 4.9 Denda Angsuran & Waiver

#### FR-34 [M]: Hitung Denda Angsuran
- Denda dihitung per Angsuran yang dilunasi: pokok yang dilunasi oleh Penerimaan ini × 0,001 × Hari Telat Angsuran tersebut, **tanpa batas atas**.
- Hari Telat = max(0, tanggal Penerimaan − tanggal jatuh tempo).
- Kurang bayar ≤ Rp250.000 dianggap lunas. Selisihnya dijurnal ke "Beban Selisih Biaya Transfer". `[ASSUMPTION]`
- Grid menampilkan per Angsuran: jatuh tempo, Hari Telat, pokok, Denda Angsuran, dan selisih biaya transfer.

#### FR-35 [M]: Waiver
Sales Admin dapat mencentang **Apply Penalty Waiver**, memilih Alasan Waiver (Pencairan KPR Bank / Promosi Special Waiver / Kewenangan Eksekutif), dan mengisi justifikasi.
- Waiver tanpa justifikasi tidak bisa disimpan.
- Waiver selalu berlaku untuk seluruh denda Penerimaan tersebut. `[ASSUMPTION]`
- Waiver dengan alasan *Kewenangan Eksekutif* menunggu CFO. Alokasi pokok tetap berjalan, tetapi jurnal denda ditahan sampai CFO memutuskan.

### 4.10 Alokasi & Notifikasi Pembeli

#### FR-36 [M]: Konfirmasi alokasi & siklus Penerimaan
**Confirm Allocation** mengalokasikan Penerimaan dengan urutan: pokok Angsuran tertua → Denda Angsuran tersebut (jika tidak di-Waiver) → Angsuran berikutnya → Titipan. `[ASSUMPTION]`

Batch Jurnal AR yang dibuat:
- Debit Bank.
- Kredit Piutang Angsuran, Kredit Piutang Denda Angsuran, dan/atau Kredit Titipan Pembeli.
- Untuk denda yang timbul dan tidak di-Waiver: Debit Piutang Denda Angsuran, Kredit Pendapatan Denda Angsuran.

Batch dikirim ke ERP mock.

Siklus status Penerimaan:

```
UNALLOCATED ──► RECOMMENDED / MANUAL_REVIEW ──(Confirm)──► ALLOCATED
ALLOCATED dengan Waiver Kewenangan Eksekutif: denda berstatus MENUNGGU_CFO ──► WAIVED / DITAGIH
```

#### FR-37 [M]: Notifikasi mock
Sistem membuat kuitansi digital (PDF), lalu menaruh pesan WhatsApp dan email ke Outbox yang bisa dilihat di UI. Tidak ada pesan yang benar-benar dikirim.

### 4.11 Dasbor Eksekutif & Antrean Staging (Layar 1)

#### FR-38 [M]: Kartu metrik
Untuk SPV terpilih (atau Semua SPV, khusus CFO), dasbor menampilkan:
- **Unallocated AR:** total Rp Penerimaan Unallocated.
- **Pending AP Audit:** total Bruto Tagihan Terverifikasi untuk Termin yang belum Posted/Rejected.
- **Flagged Disputes:** jumlah Termin berstatus Dispute, Hard Stop, dan Menunggu CFO.
- **Recon Velocity:** rata-rata menit dari unggah sampai Posted, untuk 30 hari terakhir.
- **Kebocoran Dicegah:** Σ (Net Payable Klaim − Net Payable Terverifikasi) dari Termin yang sudah Posted.

#### FR-39 [M]: Tabel antrean staging
Satu tabel gabungan Termin dan Penerimaan, berisi jenis, SPV, pihak, nilai, status, dan badge Skor Kepastian/Match Score (hijau ≥ 85%, kuning/merah < 85%).
- Aksi cepat:
  - **Review** membuka Layar 2 atau 3.
  - **Approve** hanya untuk READY atau RECOMMENDED MATCH.
  - **Flag Dispute** memindahkan READY ke DISPUTE, dengan alasan.
- Tabel bisa difilter per status, jenis, dan SPV.

#### FR-40 [M]: Antrean CFO
CFO melihat bagian khusus berisi Termin Menunggu CFO, Termin Hard Stop, dan Waiver Kewenangan Eksekutif. Dari antrean ini CFO bisa langsung membuka layar detail dan memutuskan.

### 4.12 Jejak Audit & Akurasi AI

#### FR-41 [M]: Jejak Audit tamper-evident
Setiap aksi dicatat: unggah, Override, Approve, Reject, Flag, Waiver, posting, dan keputusan CFO. Setiap entri berisi pelaku, peran, SPV, aksi, entitas, nilai awal, nilai baru, alasan, waktu UTC, dan hash yang terhubung ke entri sebelumnya.
- API tidak menyediakan cara untuk mengubah atau menghapus entri.
- [S] CFO dapat menjalankan "Verifikasi integritas". Jika ada entri yang diubah langsung di database, rantai hash dilaporkan putus.

#### FR-42 [S]: Akurasi agen AI
Untuk setiap field hasil ekstraksi, sistem menyimpan nilai dari AI dan nilai final. Akurasi = persentase field yang tidak di-Override. Angka ini ditampilkan ke CFO per jenis field.

## 5. NFR Lintas Fitur

- **Kecepatan:** pemrosesan Paket Dokumen AP 10 halaman ≤ 60 detik. Pencocokan 1.000 Penerimaan ≤ 10 detik.
- **Ketepatan angka:** semua hitungan memakai Decimal, dan tes otomatis FR-14 dan FR-31 wajib lulus.
- **Keamanan:** API key Gemini hanya ada di backend. Isolasi SPV dicek di setiap endpoint.
- **Privasi:** OCR berjalan lokal. Ke Gemini hanya dikirim teks OCR dan, jika perlu untuk klasifikasi, gambar halaman.
- **Ketahanan:** kegagalan Gemini atau ERP mock tidak menghilangkan data. Item berpindah ke status yang bisa diulang (GAGAL_PROSES / ERP_GAGAL).
- **Bahasa:** UI berbahasa Indonesia, dengan format Rupiah "Rp1.234.567".

## 6. Non-Goals

- Bukan ERP. Tidak menyimpan buku besar.
- Tidak mengeksekusi pembayaran ke bank.
- Tidak membuat e-Faktur/e-Bupot, dan tidak melapor pajak.
- Tidak menangani pelepasan Retensi (BAST II), adendum kontrak, faktur dan pemotongan pajak saat uang muka dibayar, atau multi-mata uang.
- Tidak menangani sisi pajak penjualan: PPN Keluaran dan PPh final pengalihan properti atas Penerimaan. Piutang Angsuran dianggap sudah dibukukan di luar sistem.
- Tidak ada aplikasi mobile.

## 7. Lingkup MVP

### 7.1 Termasuk
- Semua FR bertanda [M].
- FR [S] dikerjakan jika waktunya cukup, dengan urutan FR-41 verifikasi integritas → FR-21 → FR-42.
- **Data seed:**
  - 3 SPV.
  - Sekitar 6 Vendor dengan Jenis Jasa dan SBU berbeda.
  - Sekitar 8 Kontrak, termasuk Kontrak A dan B dari FR-14.
  - Sekitar 60 Unit dengan Jadwal Angsuran.
  - 1 CSV berisi sekitar 40 Penerimaan, termasuk pembayaran 2 Angsuran sekaligus, unit tetangga (C1-02/C1-03), dan baris yang memakai nomor VA.
  - PDF contoh yang dibuat dengan script, memicu setiap jenis Anomali, dengan sebagian halaman di-raster untuk menguji jalur OCR scan.

### 7.2 Tidak termasuk MVP
- SSO sungguhan, ERP SAP/Oracle/Xero sungguhan, WhatsApp/email sungguhan, dan email gateway. Semuanya disimulasikan.
- Parser MT940. Hanya CSV. `[NOTE FOR PM: tambahkan jika waktu tersisa — juri dari perbankan mungkin menanyakannya]`
- FR [C]: FR-30 webhook dan "Buat Kontrak cepat" (FR-7).

## 8. Metrik Keberhasilan (target demo)

**Utama**
- **SM-1:** Paket Dokumen AP dari unggah sampai ERP Batch Reference ID ≤ 15 menit, dengan waktu sistem ≤ 60 detik. Memvalidasi FR-3 sampai FR-28.
- **SM-2:** 100% skenario Anomali di data seed terdeteksi dengan Keparahan yang benar. Memvalidasi FR-15 sampai FR-22.
- **SM-3:** ≥ 95% Penerimaan seed yang memuat kode unit teralokasi ke Unit yang benar sebagai RECOMMENDED MATCH. Memvalidasi FR-31.

**Sekunder**
- **SM-4:** Mesin kalkulasi cocok 100% dengan Contoh A, Contoh B, dan kasus tidak bulat. Memvalidasi FR-8 sampai FR-14 dan FR-34.

**Counter-metric (jangan dioptimalkan)**
- **SM-C1:** Persentase READY / RECOMMENDED MATCH. Menaikkannya dengan melonggarkan ambang berarti menyembunyikan kebocoran. Yang dipantau justru *false green*: item hijau yang kemudian di-Override atau dialokasikan ulang. Menyeimbangkan SM-1 dan SM-3.

## 9. Pertanyaan Terbuka

1. Model Gemini mana yang dipakai: versi Flash (cepat/murah) atau Pro (lebih teliti)? Diputuskan di tahap arsitektur lewat uji coba pada PDF seed. Model bisa diganti lewat konfigurasi.
2. Apakah akses Gemini perlu dipindah ke Vertex AI region Jakarta setelah hackathon, demi residensi data? Kodenya sudah disiapkan untuk berpindah lewat konfigurasi.

## 10. Indeks Asumsi

- FR-6: Skor Kepastian = keyakinan terendah di antara Field Wajib.
- §4.3: Pembulatan half-up per baris. Pembulatan e-Faktur/e-Bupot tidak dimodelkan.
- FR-10: Tarif PPN efektif 11% disimpan sebagai konfigurasi.
- FR-31: Kemiripan huruf S_unit memakai ambang 0,80. Rumus peluruhan S_nominal di atas toleransi.
- FR-34: Kurang bayar ≤ Rp250.000 dianggap lunas, dibebankan ke Beban Selisih Biaya Transfer.
- FR-35: Waiver selalu penuh.
- FR-36: Urutan alokasi: pokok tertua → dendanya → Angsuran berikutnya → Titipan.
