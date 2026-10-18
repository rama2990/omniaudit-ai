# OmniAudit AI

OmniAudit AI adalah dasbor audit untuk developer properti dengan banyak SPV. Fungsinya:
- **AP (tagihan kontraktor):** memeriksa tagihan kontraktor terhadap BAP, kontrak, dan aturan pajak.
- **AR (pembayaran pembeli):** mencocokkan pembayaran pembeli ke unitnya.
- **CFO:** memberi CFO kontrol atas kasus besar.

Pembagian kerjanya:
- **AI (Google Gemini)** hanya membaca dokumen.
- **Kode deterministik** menghitung semua angka, termasuk pajak, retensi, uang muka, denda, dan jurnal.
- **Manusia** yang memutuskan.

- PRD: `docs/prds/prd-omniaudit-2026-10-18/prd.md`
- Desain teknis: `docs/superpowers/specs/2026-10-18-omniaudit-design.md`

## Menjalankan

Kebutuhan: Python 3.12 + [uv](https://docs.astral.sh/uv/), dan Node 20+.

```bash
cd frontend && npm install && npm run build && cd ..
cd backend && uv sync
uv run uvicorn app.main:app --port 8000
```

Buka http://localhost:8000. Pada start pertama, database diisi data seed secara otomatis, dan proses ini butuh sekitar 1 menit karena ada PDF hasil scan yang dibaca OCR.

**Mengaktifkan Gemini:** salin `backend/.env.example` menjadi `backend/.env`, lalu isi `GEMINI_API_KEY`. Tanpa key, aplikasi tetap jalan dalam **mode offline**, yaitu ekstraksi dengan pola teks lokal. Ini juga cadangan kalau internet mati saat demo.

**Reset data demo:**

```bash
cd backend && uv run python -m app.seed
```

**Tes:**

```bash
cd backend && uv run pytest
```

**Uji Gemini sungguhan pada PDF demo** (butuh API key):

```bash
cd backend && uv run python scripts/gemini_check.py
```

**Mode pengembangan frontend** (hot reload, `/api` diteruskan ke port 8000):

```bash
cd frontend && npm run dev
```

## Skrip demo

Semua file demo ada di folder `demo/`. Persona dan SPV dipilih dari dropdown di kanan atas.

**UJ-1 Overbilling (Dewi, Finance AP, PT Suburban Land One)**
1. Klik **Unggah dokumen tagihan**, pilih `demo/01_UJ1_kontrak_B_overbilling.pdf`.
2. Jejak kerja agen berjalan live. Invoice mengklaim 60%, BAP hanya 55%, jadi tagihan masuk status **Dispute**.
3. Klik ikon pin di tabel komparasi. PDF di kiri akan melompat ke angka yang dimaksud.
4. Klik **Terima koreksi & posting ke ERP**. Net Payable terverifikasi Rp234.562.500, dan muncul nomor batch ERP.

**UJ-3 Kasus CFO**
1. Sebagai Dewi, unggah `demo/02_UJ3_kontrak_A_butuh_CFO.pdf`. Klaimnya Rp2,997 M (> Rp500 jt), jadi klik **Ajukan ke CFO**.
2. Ganti persona ke Hartono (CFO), lalu buka **Ruang CFO**. Di sana ada Hard Stop klaim ganda lintas SPV dan termin yang menunggu keputusan.
3. Klik **Tinjau**, lalu **Setujui & posting ke ERP**. Net Payable terverifikasi Rp2.112.875.000.
4. Di Jejak audit, klik **Verifikasi integritas**. Lalu klik **Simulasi ubah data** untuk menunjukkan rantai hash yang putus.

**UJ-2 Rekonsiliasi (Andi, Sales Admin AR)**
1. Klik **Unggah rekening koran**, pilih `demo/rekening_koran_SLO1_2026-10-17.csv`. Hasilnya: 6 penerimaan teralokasi otomatis lewat VA, sisanya masuk antrean.
2. Tinjau baris "TRF BPK SUTRISNO BLK C1/02". Rekomendasinya unit C1-02 dengan skor 97%, telat 12 hari.
3. Centang **Hapus denda keterlambatan**, pilih alasan *Pencairan KPR Bank*, isi justifikasi, lalu klik **Konfirmasi alokasi & kirim notifikasi ke pembeli**.
4. Notifikasi WhatsApp/email beserta kuitansi PDF muncul. Semua notifikasi ini simulasi, tidak ada yang benar-benar terkirim.

**Skenario lain di antrean seed:**
- Kontrak D, hasil scan, bersih: status **Siap disetujui**.
- Kontrak C: retensi tidak dicantumkan dan tarif PPh tidak sesuai SBU. Status tetap hijau dengan badge kuning.
- Kontrak E: rincian pekerjaan tidak cocok dengan totalnya.
- Kontrak F: nominal tagihan digelembungkan.
- Kontrak G: klaim ganda lintas SPV.

**Simulasi ERP gagal:** klik chip mode di kanan atas.

## Struktur

```
backend/app/   calc (pajak & termin), audit (anomali & status), matching (Match Score),
               allocation (denda & alokasi), journal, ocr, extractor (Gemini/pola teks),
               pipeline (agen + Telemetry), ar, api, seed
frontend/src/  pages: Dashboard, ApReview (split-view), ArReconcile, Cfo
demo/          PDF tagihan contoh dan CSV rekening koran
```
