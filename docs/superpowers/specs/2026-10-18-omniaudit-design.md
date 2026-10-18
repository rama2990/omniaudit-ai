# OmniAudit AI — Design Spec

**Sumber requirement:** `D:\Project\Hackathon\docs\prds\prd-omniaudit-2026-10-18\prd.md` (v3.1 final). Spec ini hanya mencatat *bagaimana* PRD tersebut dibangun.

## Keputusan terkunci

**Disetujui user:**
- Monolith modular: satu proses FastAPI dengan database SQLite.
- Pemrosesan berjalan sebagai background task di proses yang sama, dan Telemetry dikirim lewat SSE.
- AI memakai Gemini lewat Google AI Studio dengan SDK `google-genai`. Model diatur di config, dan bisa dialihkan ke Vertex lewat env.
- OCR lokal: PyMuPDF untuk PDF digital, RapidOCR untuk hasil scan (CPU, pip saja, tanpa Tesseract).
- Frontend: React + Vite + TypeScript + MUI dengan gaya Material/Google.
- Demo di laptop lokal. Strukturnya siap menjadi satu container Cloud Run: FastAPI juga menyajikan `frontend/dist`.

**Diputuskan sendiri karena user minta tidak ditanya lagi:**
- **`GEMINI_MODE=fake`** memakai extractor deterministik berbasis pola teks OCR. Dipakai untuk tes, untuk verifikasi tanpa API key, dan sebagai cadangan kalau internet mati saat demo. UI menampilkan chip "Mode offline". Mode default `auto`: memakai Gemini kalau `GEMINI_API_KEY` ada, dan fake kalau tidak.
- Model default `gemini-flash-latest`, bisa diganti lewat `GEMINI_MODEL`.
- Tanpa React Query dan tanpa state library. Cukup `fetch` dan hook kecil.
- Database dibuat ulang dari seed lewat `python -m app.seed`. File database ada di `backend/data/`.

## Struktur

```
backend/app/
  money.py       Decimal helper (rupiah, round half-up)
  calc.py        FR-8..14 termin, FR-34 denda angsuran        (murni)
  audit.py       FR-15..22 anomali, FR-23 status               (murni)
  matching.py    FR-31 Match Score, normalisasi unit, JW        (murni)
  allocation.py  FR-36 alokasi FIFO + denda + waiver            (murni)
  journal.py     Batch Jurnal AP & AR (berimbang atau error)    (murni)
  ocr.py         kata + bbox per halaman
  extractor.py   Gemini / fake → field + word_ids + confidence; grounding check
  pipeline.py    orkestrasi AP + Telemetry
  db.py models.py  SQLModel
  auditlog.py    hash chain
  mocks.py       ERP mock, Outbox, kuitansi PDF
  api.py         semua router; dependency persona/SPV
  seed.py        data seed + PDF contoh (reportlab)
backend/tests/   pytest
frontend/src/    pages: Dashboard, ApReview, ArReconcile, Cfo (+ AuditLog)
```

## Prinsip

- Modul yang ditandai (murni) tidak mengakses database atau jaringan, dan diuji dengan TDD terhadap contoh-contoh di PRD.
- Saldo Uang Muka, Progres Sebelumnya, dan Σ denda yang sudah dipotong selalu diturunkan dari Termin yang POSTED. Tidak ada kolom mutable untuk nilai-nilai ini.
- Persona dikirim lewat header `X-Persona`. Setiap endpoint memeriksa peran dan SPV, dan menolak dengan 403.

## Error

| Kejadian | Penanganan |
|---|---|
| Gemini gagal | Diulang 1 kali, lalu `GAGAL_PROSES` dengan opsi proses ulang. Hasil OCR disimpan. |
| Halaman tidak terbaca | Keyakinan field = 0, sehingga Termin jadi Dispute. |
| ERP mock gagal (saklar `erp_fail` di admin/demo) | `ERP_GAGAL` dengan opsi kirim ulang. |
| Konfirmasi AR | Satu transaksi database. |

## Tes

- Unit test: `calc`, `audit`, `matching`, `allocation`, `journal`.
- API test memakai `GEMINI_MODE=fake`: isolasi SPV, siklus Termin, dan konfirmasi AR.
- Script `scripts/gemini_check.py` untuk menguji Gemini sungguhan pada PDF seed.
- Verifikasi akhir: menjalankan UJ-1, UJ-2, dan UJ-3 di browser.
