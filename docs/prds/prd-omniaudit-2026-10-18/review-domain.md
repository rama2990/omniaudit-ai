# Review Domain — PRD OmniAudit AI v3.0 (draft)

**Reviewer:** adversarial review domain (akuntansi developer properti, pajak jasa konstruksi, rekonsiliasi penerimaan bank)
**Tanggal:** 2026-10-18
**Dokumen yang direview:** `D:\Project\Hackathon\docs\prds\prd-omniaudit-2026-10-18\prd.md` (fokus §4.3, §4.4, §4.8–4.10) dan `D:\Project\Hackathon\docs\prds\prd-omniaudit-2026-10-18\addendum.md`

**Keputusan yang sudah final dan TIDAK dipersoalkan di sini** (hanya dicek konsistensinya): retensi 5% atas DPP; potongan uang muka proporsional (UM% × DPP termin); ambang CFO = nilai bruto klaim invoice > Rp500 jt; Denda Angsuran 1‰/hari tanpa batas; PPN 11% efektif sebagai konfigurasi; progres kumulatif.

## Verdict

**Lulus dengan perbaikan wajib.** Contoh FR-12 dan jurnalnya benar sampai ke rupiah dan berimbang. Namun angka contoh sengaja "bulat", sehingga menyembunyikan satu bug pembulatan yang membuat ±10% transaksi nyata menghasilkan jurnal tidak berimbang (FR-22 akan menolak posting). Ada juga beberapa celah logika (Net Payable bisa negatif, saldo uang muka tidak terdefinisi, kontradiksi FR-6 vs FR-15/FR-17) dan satu pernyataan pajak yang salah faktual ("tarif PPh pada faktur").

**Jumlah temuan:** Critical 1 · High 7 · Medium 12 · Low 10

---

## 1. Verifikasi angka contoh FR-12

Dihitung ulang dengan `decimal.Decimal`, pembulatan half-up per baris.

Input: Nilai Kontrak 11.100.000.000 → DPP Kontrak 10.000.000.000. Hari Terlambat = 10-10-2026 − 30-09-2026 = **10 hari** (benar).

| Baris | Klaim (80% − 50% = 30%) | PRD | BAP (75% − 50% = 25%) | PRD |
|---|---:|:---:|---:|:---:|
| Nilai Termin Bruto | 11,1 M × 30% = 3.330.000.000 | ✓ | 11,1 M × 25% = 2.775.000.000 | ✓ |
| DPP (÷1,11) | 3.000.000.000 | ✓ | 2.500.000.000 | ✓ |
| PPN 11% | 330.000.000 | ✓ | 275.000.000 | ✓ |
| Retensi 5% × DPP | 150.000.000 | ✓ | 125.000.000 | ✓ |
| Potongan UM 10% × DPP | 300.000.000 | ✓ | 250.000.000 | ✓ |
| Denda: 10 M × 2‰ × 10 = 200 jt; batas 10 M × 5% = 500 jt → 200 jt | 200.000.000 | ✓ | 200.000.000 | ✓ |
| PPh 4(2) 2,65% × DPP | 79.500.000 | ✓ | 66.250.000 | ✓ |
| Net Payable | 3.330 − 150 − 300 − 200 − 79,5 = **2.600.500.000** | ✓ | 2.775 − 125 − 250 − 200 − 66,25 = **2.133.750.000** | ✓ |

**Jurnal (kolom BAP):**
Debit: 2.500.000.000 + 275.000.000 = **2.775.000.000**.
Kredit: 125.000.000 + 250.000.000 + 200.000.000 + 66.250.000 + 2.133.750.000 = **2.775.000.000**. Berimbang ✓.

**Kesimpulan:** tidak ada salah hitung di contoh. Masalahnya ada di aturan yang tidak teruji oleh angka bulat ini (lihat C1, H1, M2).

---

## 2. Critical

### C1 — Pembulatan per baris membuat DPP + PPN ≠ Nilai Termin Bruto, sehingga jurnal tidak berimbang
- **Lokasi:** §4.3 Deskripsi (pembulatan per baris), FR-8, FR-22.
- **Masalah:** FR-8 menghitung DPP = round(Bruto ÷ 1,11) lalu PPN = round(DPP × 11%) secara terpisah. Jurnal mendebit DPP + PPN, sedangkan total kredit selalu = Bruto (karena Net Payable = Bruto − potongan). Saya uji 200 nilai Bruto berturut-turut (1.000.000 s/d 1.000.199): **20 kasus (10%) selisih Rp1**. Contoh: Bruto 1.000.196 → DPP 901.077, PPN 99.118, jumlah 1.000.195. FR-22 melarang batch tidak berimbang, jadi posting akan gagal secara acak. Contoh FR-12 lolos hanya karena angkanya bulat.
- **Perbaikan:** tetapkan **PPN = Bruto − DPP** (PPN sebagai sisa), bukan DPP × tarif. Tambahkan contoh tes kedua dengan angka tidak bulat (misalnya Nilai Kontrak 7.345.678.901, progres 37,5% → 61,25%) di NFR "Ketepatan angka", plus tes properti "DPP + PPN = Bruto untuk semua Bruto".

---

## 3. High

### H1 — Net Payable bisa negatif bila denda kumulatif melebihi nilai termin
- **Lokasi:** FR-11, FR-12.
- **Masalah:** Denda dihitung atas DPP **seluruh Kontrak**, sedangkan termin bisa kecil. Contoh: kontrak yang sama, termin 50% → 52% (Bruto 222 jt), terlambat 25 hari → denda 500 jt (sudah kena batas). Net Payable = 222 − 10 − 20 − 500 − 5,3 = **−313.300.000**. Jurnal lalu mengkredit Utang Usaha negatif. PRD tidak mengatur ini.
- **Perbaikan:** Potongan Denda Termin = min(Denda tertunggak, Bruto − Retensi − Potongan UM − PPh). Sisa denda otomatis terbawa ke termin berikutnya (rumus FR-11 "Denda Kumulatif − denda yang sudah dipotong" sudah mendukung ini asal yang dicatat adalah denda yang **benar-benar** dipotong). Tampilkan info "Sisa denda belum terpotong Rp…". Jika Progres Disetujui = 100% dan masih ada sisa denda → anomali HIGH (Dispute).

### H2 — Saldo awal Uang Muka tidak terdefinisi, dan PPN/PPh atas porsi uang muka berpotensi dihitung dua kali
- **Lokasi:** FR-10, Glosarium "Uang Muka", FR-23, jurnal FR-12.
- **Masalah:**
  1. "Sisa Saldo Uang Muka Kontrak" tidak punya nilai awal. Jika saldo awal = 10% × Nilai Kontrak (termasuk PPN) = 1,11 M, sedangkan pengembalian total = 10% × DPP seluruh termin = 1,0 M, maka **110 jt tidak pernah terpotong**. Jika saldo awal = 10% × DPP Kontrak = 1,0 M, angkanya pas.
  2. Di Indonesia, PPN terutang atas pembayaran uang muka (UU PPN Pasal 11 ayat 2 → ada Faktur Pajak Uang Muka) dan PPh 4(2) dipotong saat uang muka dibayar (PP 9/2022). Praktiknya, faktur termin berikutnya dibuat atas DPP termin **dikurangi** porsi uang muka, dan PPh termin juga atas dasar itu. PRD menghitung PPN dan PPh termin atas DPP penuh. Kalau uang muka di seed dianggap sudah difaktur dan dipotong PPh, maka PPN Masukan dan PPh dobel atas porsi uang muka. Juri berlatar pajak kemungkinan besar menanyakan ini.
- **Perbaikan (pilih satu):**
  - **(a) Penyederhanaan demo — minimal wajib:** tambahkan `[ASSUMPTION]` di FR-10 dan §10: "Saldo UM awal = Persen UM × DPP Kontrak. Untuk demo, PPN dan PPh termin dihitung atas DPP termin penuh. Praktik riil: faktur dan PPh termin atas (DPP − Potongan UM) karena UM sudah difaktur dan dipotong saat dibayar." Angka contoh FR-12 tidak berubah.
  - **(b) Benar secara pajak:** PPN dan PPh dihitung atas (DPP − Potongan UM). Kolom BAP menjadi: DPP termin 2.500.000.000; Potongan UM 250.000.000; DPP faktur 2.250.000.000; PPN 247.500.000; Bruto tagihan 2.497.500.000; Retensi 125.000.000; Denda 200.000.000; PPh 59.625.000; **Net Payable 2.112.875.000**. Jurnal: Debit Persediaan 2.500.000.000 + PPN Masukan 247.500.000 = 2.747.500.000; Kredit UM 250.000.000 + Retensi 125.000.000 + Denda 200.000.000 + PPh 59.625.000 + Utang Usaha 2.112.875.000 = 2.747.500.000 (berimbang). Keputusan "UM% × DPP termin" tetap dipakai.
  - Rekomendasi: (a) untuk hackathon, karena tidak mengubah contoh; siapkan jawaban lisan (b) untuk juri.

### H3 — Kontradiksi FR-6 vs FR-15/FR-17: anomali MEDIUM tidak akan pernah masuk Jalur Hijau
- **Lokasi:** FR-5 (daftar field kritis), FR-6, FR-15, FR-17, FR-18.
- **Masalah:** FR-5 memasukkan "retensi yang tercantum" dan "tarif PPh" ke field kritis. FR-6: satu field kritis tidak ditemukan → Skor Kepastian 0% → FR-18: Dispute. Padahal kasus Omisi Retensi (FR-15) justru berarti retensi **tidak tercantum** di invoice. Jadi FR-15 selalu jatuh ke Dispute, bukan Jalur Hijau dengan badge kuning seperti asumsi FR-18. Hal yang sama terjadi bila invoice tidak mencantumkan PPh.
- **Perbaikan:** pisahkan dua kelompok di FR-5: **field wajib** (nomor invoice, NPWP, nomor kontrak, Progres Klaim, Progres BAP, tanggal BAP, nilai bruto) dan **field opsional** (retensi tercantum, PPh tercantum, line item). Skor Kepastian hanya dihitung dari field wajib. Field opsional yang tidak ada = nilai `null` yang sah (memicu FR-15/FR-17), bukan keyakinan 0.

### H4 — "Tarif PPh pada faktur" salah secara faktual
- **Lokasi:** FR-5, FR-17.
- **Masalah:** Faktur Pajak hanya memuat PPN (NSFP, NPWP, DPP, PPN). PPh 4(2) tidak tercantum di Faktur Pajak. Bukti Potong PPh justru diterbitkan oleh developer (pemotong), bukan vendor. Tarif/nilai PPh hanya mungkin muncul di **invoice** vendor. Juri pajak akan langsung menangkap ini.
- **Perbaikan:** ganti menjadi "tarif/nilai PPh 4(2) yang tercantum di invoice". Untuk Faktur Pajak, ekstrak NSFP, NPWP penjual, DPP, dan PPN (dipakai di M7).

### H5 — Tidak ada pemeriksaan "nilai tagihan vs progres klaim"; isi kolom Klaim Invoice ambigu
- **Lokasi:** FR-8, FR-12 (kolom Klaim Invoice), FR-16, FR-18 (ambang CFO).
- **Masalah:** Kolom "Klaim Invoice" dihitung ulang = Nilai Kontrak × (Progres Klaim − Sebelumnya). Kontraktor yang mencantumkan progres benar (75%) tapi nominal tagihan digelembungkan tidak tertangkap: FR-13 tidak terpicu (progres sama), FR-16 hanya membandingkan bruto dengan jumlah line item (bisa sama-sama digelembungkan). Selain itu tidak jelas apakah ambang CFO > Rp500 jt memakai nominal tertulis di invoice atau hasil hitung ulang.
- **Perbaikan:** tambahkan anomali baru (misal FR-16b) **"Nilai Tagihan Tidak Sesuai Progres"**: nilai bruto tertulis di invoice ≠ Nilai Kontrak × (Progres Klaim − Progres Sebelumnya), toleransi Rp1.000 → HIGH. Nyatakan eksplisit bahwa kolom Klaim = hasil hitung sistem dari Progres Klaim. Ambang CFO = max(bruto tertulis di invoice, bruto hasil hitung klaim) agar tidak bisa diakali.

### H6 — Dua termin terbuka pada kontrak yang sama dihitung dari baseline yang sama
- **Lokasi:** FR-8, FR-10, FR-11, FR-23.
- **Masalah:** Progres Sebelumnya, saldo UM, dan denda yang sudah dipotong baru diperbarui saat posting berhasil (FR-23). Jika termin ke-2 diunggah saat termin ke-1 masih Dispute / menunggu CFO / gagal ERP ("Kirim ulang"), keduanya dihitung dari Progres Sebelumnya yang sama → progres yang tumpang tindih ditagih dua kali, UM dan denda dipotong dua kali dari saldo yang sama.
- **Perbaikan:** satu termin terbuka per kontrak. Termin baru pada kontrak yang punya termin belum diposting → Dispute dengan pesan "Termin sebelumnya belum diposting". Saat posting, hitung ulang FR-8..FR-12 dari baseline terbaru dan tolak bila hasilnya berubah tanpa review.

### H7 — Skenario demo UJ-1/UJ-3 bertentangan dengan contoh FR-12 dan aturan CFO FR-18
- **Lokasi:** §2.3 UJ-1, UJ-3; FR-12; FR-18.
- **Masalah:** UJ-1 memakai angka FR-12 (klaim 80% vs BAP 75%). Bruto klaimnya Rp3,33 M > Rp500 jt, dan statusnya Dispute (overbilling). Menurut FR-18 tombol pasti "Ajukan ke CFO", bukan "Post to ERP" seperti alur utama UJ-1. UJ-3 menyebut CFO menyetujui "Dispute Rp1,2 M yang diajukan Dewi", angka yang tidak ada di mana pun. Skrip demo akan meleset di depan juri.
- **Perbaikan:** pilih salah satu: (a) UJ-1 jalur utama = "Ajukan ke CFO" dengan Rp3,33 M, UJ-3 menyetujui Rp3,33 M itu; atau (b) tambahkan kontrak seed kedua yang lebih kecil (bruto klaim < Rp500 jt) untuk alur Post to ERP langsung, dan pakai FR-12 sebagai kasus CFO. Samakan angka di UJ-3.

---

## 4. Medium

### M1 — Pembagi 1,11 di-hardcode padahal tarif PPN adalah konfigurasi; istilah "DPP" ambigu di rezim 12%
- **Lokasi:** Glosarium "DPP", FR-8, FR-11, §10.
- **Masalah:** "DPP = Bruto ÷ 1,11" dan "DPP Kontrak = Nilai Kontrak ÷ 1,11" tidak ikut berubah jika konfigurasi PPN diubah. Di rezim PMK 131/2024 (PPN 12% × DPP Nilai Lain 11/12), istilah "DPP" resmi di faktur adalah 11/12 × harga jual. Yang PRD sebut "DPP" sebenarnya **Harga Jual/Penggantian (nilai sebelum PPN)**. Ini yang benar untuk dasar PPh 4(2) ("jumlah pembayaran tidak termasuk PPN"), tetapi developer bisa salah memakai DPP Nilai Lain untuk PPh dan retensi.
- **Perbaikan:** rumus DPP = Bruto ÷ (1 + tarif PPN efektif). Tambahkan catatan di glosarium: "DPP di PRD ini = nilai sebelum PPN (harga jual). DPP Nilai Lain 11/12 hanya untuk tampilan faktur. Dasar PPh, retensi, UM, dan denda = nilai sebelum PPN." Simpan Nilai Kontrak sebagai DPP + PPN terpisah di master Kontrak.

### M2 — Termin terakhir dan pergeseran pembulatan kumulatif
- **Lokasi:** FR-8, FR-10.
- **Masalah:** Bruto tiap termin dibulatkan sendiri-sendiri, jadi jumlah semua termin bisa berbeda beberapa rupiah dari Nilai Kontrak. Potongan UM = min(UM% × DPP, sisa saldo) bisa menyisakan saldo Rp1–Rp beberapa yang tidak pernah habis setelah progres 100%.
- **Perbaikan:** hitung secara kumulatif: Bruto termin n = round(Nilai Kontrak × Progres Disetujui n) − Σ Bruto yang sudah diposting. Pada Progres Disetujui = 100%, Potongan UM = seluruh sisa saldo.

### M3 — Syarat "Progres < 100%" pada FR-15 tidak konsisten dengan FR-10
- **Lokasi:** FR-15 vs FR-10, §6 Non-Goals.
- **Masalah:** FR-10 selalu memotong retensi, termasuk pada termin 100% (retensi baru dilepas di BAST II, yang di luar lingkup). FR-15 tidak memunculkan anomali saat progres 100% walau invoice tidak mencantumkan retensi. Akibatnya sistem diam-diam memotong retensi tanpa badge, dan Net Payable sistem berbeda dari invoice tanpa penjelasan.
- **Perbaikan:** hapus syarat "Progres < 100%" dari FR-15.

### M4 — Kasus tepi progres belum lengkap; status "ditolak" tidak ada di FR-18
- **Lokasi:** FR-8, FR-13, FR-18.
- **Masalah:**
  1. Progres Klaim ≤ Progres Sebelumnya sering terjadi karena invoice mencantumkan progres **termin ini** (inkremental), bukan kumulatif. FR-8 langsung "ditolak", padahal status ini tidak ada di FR-18 (hanya Hijau/Dispute/Hard Stop).
  2. Progres > 100% tidak dibatasi.
  3. Rumus FR-8 hanya memakai Progres Disetujui, padahal kolom Klaim memakai Progres Klaim.
- **Perbaikan:** (1) jadikan Dispute dengan pesan "Progres klaim ≤ progres sebelumnya — kemungkinan progres inkremental", dan minta FR-5 mengekstrak progres kumulatif secara eksplisit. (2) Progres > 100% → Dispute. (3) Tulis rumus FR-8 dengan parameter P ∈ {Progres Klaim, Progres Disetujui}.

### M5 — Kontrak tidak ditemukan → Dispute, tetapi kalkulasi tidak bisa jalan
- **Lokasi:** FR-7, FR-12, FR-20, §9 #3.
- **Masalah:** Tanpa Nilai Kontrak, FR-8..FR-12 tidak bisa dihitung. Layar split-view dan CFO tidak tahu apa yang harus ditampilkan.
- **Perbaikan:** nyatakan bahwa kolom kalkulasi kosong dan posting dinonaktifkan sampai kontrak dihubungkan (manual pilih atau "Buat Kontrak cepat", sesuai Pertanyaan Terbuka #3).

### M6 — Nama akun jurnal AP kurang tepat untuk developer
- **Lokasi:** jurnal FR-12, FR-31.
- **Masalah:** Untuk developer yang membangun unit untuk dijual, biaya konstruksi masuk **Persediaan / Aset Real Estat – Bangunan dalam Penyelesaian**, bukan KDP (KDP = aset tetap milik sendiri) dan bukan "Beban". Denda keterlambatan kontraktor sering diperlakukan sebagai pengurang biaya perolehan, bukan pendapatan. Akun "Pendapatan Denda" juga dipakai di AR (FR-31), sehingga dua jenis denda bercampur.
- **Perbaikan:** debit "Aset Real Estat – Bangunan dalam Penyelesaian (KDP untuk aset sendiri)". Kredit denda kontraktor ke "Pendapatan Lain-lain – Denda Kontraktor" (atau pengurang Aset Real Estat sebagai pilihan kebijakan), terpisah dari "Pendapatan Denda Angsuran" di AR. Untuk demo cukup ganti label.

### M7 — Tidak ada pemeriksaan Faktur Pajak, padahal PPN Masukan dijurnal
- **Lokasi:** §4.4 tabel anomali, FR-5, jurnal FR-12.
- **Masalah:** PPN Masukan hanya sah dikreditkan dengan Faktur Pajak yang valid. Tidak ada aturan untuk faktur hilang, PPN di faktur ≠ PPN hitungan, atau NPWP faktur ≠ NPWP master.
- **Perbaikan:** tambahkan anomali MEDIUM "Faktur Pajak tidak sesuai": faktur tidak ada / PPN faktur ≠ PPN hitungan (toleransi Rp1) / NPWP berbeda. Badge kuning dan catatan "PPN Masukan belum dapat dikreditkan".

### M8 — S_nominal gagal untuk satu transfer yang membayar beberapa angsuran sekaligus
- **Lokasi:** FR-26 S_nominal, FR-31, SM-3.
- **Masalah:** S_nominal hanya dibandingkan dengan angsuran tertua. Pembeli yang membayar 2 angsuran @Rp5 jt sekaligus (Rp10 jt): S_nominal = 1 − (5.000.000 − 250.000) ÷ 5.000.000 = 0,05. Match Score maksimum = 0,45 + 0,35 + 0,01 = **81%** → Manual Review, walaupun unit dan nama cocok sempurna. Ini kasus yang sangat umum (pembeli menunggak lalu melunasi).
- **Perbaikan:** S_nominal = nilai terbaik dari perbandingan dengan Σ k angsuran tertua yang belum lunas (k = 1..n), serta angsuran + denda berjalan. Tambahkan skenario ini di data seed.

### M9 — Ambang Jaro-Winkler 0,80 untuk kode unit terlalu longgar
- **Lokasi:** FR-26 S_unit, FR-27.
- **Masalah:** Kode unit pendek dan hanya beda satu digit dengan unit tetangga. JW("C1-02", "C1-03") = 0,92 dan JW("C1-02", "C2-02") = 0,88, jadi unit yang **salah** mendapat S_unit 0,7. Investor yang punya dua unit berdampingan bisa membuat dua kandidat sama-sama ≥ 85%. Sebaliknya, "C1-2" vs "C1-02" (beda nol di depan) seharusnya cocok persis tetapi hanya mendapat 0,7.
- **Perbaikan:** normalisasi nol di depan ("C1-2" → "C1-02"). Fuzzy hanya untuk huruf blok/tower, angka nomor unit harus sama persis. RECOMMENDED MATCH hanya jika kandidat teratas ≥ 85% **dan** unggul ≥ 10 poin dari kandidat kedua. Jika tidak, Manual Review.

### M10 — Denda Angsuran: dasar, pembayaran parsial, dan toleransi Rp250 rb belum terdefinisi
- **Lokasi:** FR-29, FR-31.
- **Masalah:** Rumus memakai "nilai angsuran" penuh dan satu tanggal jatuh tempo. Jika pembeli sudah membayar sebagian tepat waktu, denda atas angsuran penuh terlalu besar. Jika satu transfer melunasi beberapa angsuran (FIFO), tiap angsuran punya jatuh tempo dan denda sendiri. "Selisih yang tercakup toleransi biaya admin" tidak didefinisikan: kurang bayar ≤ Rp250 rb dianggap lunas (dibebankan sebagai biaya admin) atau tetap terutang dan memicu denda bulan berikutnya?
- **Perbaikan:** Denda dihitung **per angsuran** = bagian pokok yang dilunasi penerimaan ini × 0,001 × Hari Telat angsuran itu. Tetapkan: kurang bayar ≤ Rp250.000 dianggap lunas, dan selisihnya dijurnal ke akun "Selisih Biaya Transfer" (asumsi). Tambahkan ke §10.

### M11 — Alokasi AR: urutan denda vs pokok, waiver menunggu CFO, dan auto-alokasi VA
- **Lokasi:** FR-24, FR-30, FR-31.
- **Masalah:**
  1. Jika pembeli mentransfer angsuran + denda, FIFO hanya ke angsuran, sehingga kelebihannya menjadi titipan sementara piutang denda tetap terbuka.
  2. Waiver "Kewenangan Eksekutif" butuh CFO, tetapi tidak jelas apakah alokasi ditahan atau dijurnal dulu.
  3. Penerimaan VA yang cocok persis langsung teralokasi (FR-24), tanpa disebutkan apakah denda, waiver, jurnal, dan notifikasi tetap berjalan.
- **Perbaikan:** (1) tetapkan urutan alokasi: pokok angsuran tertua → denda angsuran itu → angsuran berikutnya → titipan, atau tetapkan bahwa pembayaran tidak melunasi denda (pilih satu dan catat sebagai asumsi). (2) Alokasi pokok jalan, jurnal denda ditahan dengan status "Menunggu CFO". (3) Auto-alokasi VA tetap menjalankan FR-29 dan FR-31; jika ada denda, masuk antrean untuk keputusan waiver.

### M12 — Klaim Ganda: cakupan "SPV mana pun" memicu Hard Stop pada dokumen sendiri
- **Lokasi:** FR-14.
- **Masalah:** "SPV mana pun" juga mencakup SPV yang sama, termasuk unggah ulang setelah Reject, retry ERP, atau koreksi invoice dengan nomor sama. Semua ini memicu Hard Stop CRITICAL yang hanya bisa dibuka CFO. NPWP 15 digit vs 16 digit (format sejak 2024) dan variasi penulisan nomor invoice juga bisa membuat duplikat lolos.
- **Perbaikan:** bandingkan hanya dengan termin lain yang tidak berstatus Rejected dan bukan entitas yang sama. Beda SPV → CRITICAL, sama SPV → HIGH (Dispute). Normalisasi NPWP ke 16 digit dan nomor invoice (huruf besar, buang spasi/tanda baca) sebelum dibandingkan.

---

## 5. Low

### L1 — Metode pembulatan
- **Lokasi:** §4.3 Deskripsi.
- **Masalah:** Tidak jelas apakah baris turunan (retensi, UM, PPh) memakai DPP yang sudah dibulatkan. e-Faktur/e-Bupot membulatkan ke bawah, sehingga half-up bisa berbeda Rp1. Untuk demo ini dapat diterima.
- **Perbaikan:** tulis "baris turunan memakai DPP yang sudah dibulatkan" dan catat perbedaan dengan e-Faktur/e-Bupot sebagai penyederhanaan.

### L2 — Tabel PPh FR-9 sudah benar
- **Lokasi:** FR-9.
- **Catatan:** tarif sesuai PP 9/2022: pelaksanaan 1,75% / 2,65% / 4%; konsultansi 3,5% / 6%. Satu kategori belum ada, yaitu pekerjaan konstruksi terintegrasi (2,65% dengan SBU, 4% tanpa SBU). Ini opsional. Perlu dicatat juga bahwa "Tanpa SBU" mencakup perorangan tanpa SKK.

### L3 — Definisi Progres Sebelumnya
- **Lokasi:** Glosarium.
- **Masalah:** Belum ditegaskan bahwa Progres Sebelumnya adalah Progres **Disetujui** yang diposting, bukan Progres Klaim.
- **Perbaikan:** tegaskan di glosarium. Pada contoh FR-12, termin berikutnya memakai baseline 75%, bukan 80%.

### L4 — Override progres melebihi bukti
- **Lokasi:** FR-21.
- **Masalah:** Override Progres Disetujui bisa diisi di atas min(Klaim, BAP).
- **Perbaikan:** blokir nilai di atas min(Klaim, BAP), atau jadikan Dispute yang wajib disetujui CFO.

### L5 — Kunci duplikat CSV terlalu longgar
- **Lokasi:** FR-24.
- **Masalah:** Kunci duplikat (tanggal + nominal + berita) membuang dua transfer sah yang identik. Contohnya, satu pembeli membayar dua unit dengan nominal sama di hari yang sama.
- **Perbaikan:** tambahkan nama pengirim dan nomor referensi bank (jika ada) ke kunci duplikat, atau tandai baris itu "kemungkinan duplikat" alih-alih membuangnya.

### L6 — Asumsi jurnal AR belum dinyatakan
- **Lokasi:** FR-31.
- **Masalah:** "Kredit Piutang Angsuran" mengandaikan piutang (termasuk PPN Keluaran) sudah dibukukan di luar sistem. PPN Keluaran atas pembayaran sebelum serah terima dan PPh final 2,5% (PP 34/2016) tidak dimodelkan.
- **Perbaikan:** catat sebagai asumsi/non-goal di §6 dan §10.

### L7 — Urutan prioritas jalur
- **Lokasi:** FR-18.
- **Masalah:** Urutan prioritas antar-status belum disebutkan.
- **Perbaikan:** nyatakan urutannya: CRITICAL > HIGH/Skor < 85% > MEDIUM.

### L8 — Kalibrasi Match Score untuk demo
- **Lokasi:** FR-26, UJ-2, SM-3.
- **Masalah:** Tanpa kode unit di berita transfer, Match Score maksimum = 55%, jadi selalu Manual Review. Data seed harus memuat kode unit agar SM-3 ≥ 95% tercapai. Angka "93%" di UJ-2 juga belum pasti bisa direproduksi. Contoh: JW("SUTRISNO", "SUTRISNO WIBOWO") = 0,907, sehingga S_nominal ≈ 0,81 diperlukan.
- **Perbaikan:** tetapkan nominal transfer seed agar skor tepat 93%, lalu jadikan tes.

### L9 — Batas definisi line item
- **Lokasi:** FR-16.
- **Masalah:** Belum jelas apakah jumlah line item termasuk atau tidak termasuk PPN.
- **Perbaikan:** tegaskan perbandingannya: Σ line item (sebelum PPN) + PPN = bruto.

### L10 — Metrik kartu Pending AP Audit
- **Lokasi:** FR-33.
- **Masalah:** "Pending AP Audit: total Nilai Termin Bruto" tidak menyebut kolom mana yang dipakai.
- **Perbaikan:** pakai kolom Terverifikasi (atau tampilkan keduanya), supaya konsisten dengan narasi "kebocoran yang dicegah = Klaim − Terverifikasi".

---

## 6. Pengecekan konsistensi keputusan final (tidak ada masalah)

- Retensi 5% × DPP, UM% × DPP termin, PPN 11% efektif (sesuai PMK 131/2024, 12% × 11/12): konsisten di FR-10, FR-12, dan jurnal. Catatan terkait ada di H2 dan M1.
- Ambang CFO pada bruto klaim > Rp500 jt: konsisten di §2.2, FR-18, dan FR-35. Masalah terkait ada di H5 (sumber angka) dan H7 (skenario demo).
- Denda Angsuran 1‰/hari tanpa batas: konsisten di FR-29. Masalah terkait ada di M10 (dasar perhitungan).
- Progres kumulatif: konsisten. Kasus tepi ada di M4.
