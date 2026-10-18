# OmniAudit AI Implementation Plan

> **For agentic workers:** Dieksekusi inline di sesi pembuat (user tidur, minta tanpa pertanyaan). Langkah memakai checkbox.

**Goal:** Membangun aplikasi demo OmniAudit AI sesuai PRD v3.1 (AP audit + AR rekonsiliasi + dasbor CFO).

**Architecture:** FastAPI monolith + SQLite (SQLModel). Modul murni untuk kalkulasi, audit, matching, alokasi, dan jurnal. OCR lokal → Gemini/fake extractor → pipeline dengan Telemetry SSE. React + Vite + MUI disajikan oleh FastAPI saat build.

**Tech Stack:** Python 3.12 + uv, FastAPI, SQLModel, PyMuPDF, RapidOCR (onnxruntime), google-genai, reportlab, jellyfish (Jaro-Winkler), pytest; React 18 + TS + Vite + MUI + MUI X DataGrid + react-pdf.

## Global Constraints
- Semua uang memakai `decimal.Decimal`, dibulatkan ke rupiah penuh half-up per baris. Float dilarang di jalur uang.
- Istilah UI mengikuti Glosarium PRD. Bahasa UI Indonesia, format `Rp1.234.567`.
- API key hanya di `backend/.env`. `GEMINI_MODE` = `auto|gemini|fake`.
- Setiap endpoint memeriksa persona (`X-Persona`), peran, dan SPV. Pelanggaran dijawab 403.

---

### Task 1: money + calc (FR-8..14) — TDD
**Files:** `backend/app/money.py`, `backend/app/calc.py`, `backend/tests/test_calc.py`
**Produces:**
- `rp(x) -> Decimal`
- `ContractTerms(dpp_kontrak, ret_pct, um_pct, target_date, denda_harian, denda_cap, pph_rate)`
- `PostedHistory(np_sum, um_sum, pen_sum)`
- `compute_termin(terms, history, p: Decimal, bap_date, ppn_rate=Decimal("0.11")) -> TerminCalc` dengan field `np, um, dpp_faktur, ppn, bruto, ret, pen, pph, net, late_days, pen_outstanding_after`
- `pph_rate(jenis, sbu) -> Decimal`

**Tes:**
- Contoh A, kedua kolom.
- Contoh B, kedua kolom.
- Carry denda: Net = 0, pen = 185.030.000.
- Termin 100% mengambil seluruh sisa Saldo UM.
- Properti: 1.000 input acak → np + ppn == um + ret + pen + pph + net, dan net ≥ 0.
- Tabel PPh lengkap.

### Task 2: audit (FR-15..23) — TDD
**Files:** `backend/app/audit.py`, `backend/tests/test_audit.py`
**Produces:**
- `Anomaly(code, severity, message)`
- `run_rules(ctx: AuditContext) -> list[Anomaly]`
- `decide_status(anoms, confidence) -> "READY"|"DISPUTE"|"HARD_STOP"`
- `needs_cfo(bruto_tertulis, bruto_klaim) -> bool`
- `ALLOWED` (tabel transisi) dan `transition(status, action, role) -> new_status`, yang memunculkan `Forbidden`/`InvalidTransition`
- `norm_invoice(s)` dan `norm_npwp(s)`

**Tes:**
- Satu tes per anomali.
- Urutan prioritas status.
- needs_cfo memakai max(...) > 500 jt.
- Transisi: AP tidak bisa membuka HARD_STOP, sedangkan CFO bisa.

### Task 3: matching + allocation + journal (FR-31, 34–36, 27) — TDD
**Files:** `backend/app/matching.py`, `allocation.py`, `journal.py`, plus tes masing-masing.
**Produces:**
- `norm_unit(s)`, `extract_unit_codes(memo) -> list[str]`, `s_unit(a, b)`, `s_nama(a, b)`
- `s_nominal(amount, installments_unpaid)`
- `score_receipt(receipt, units) -> list[Candidate]` (3 teratas) dan `match_status(cands)`
- `allocate(amount, date, installments, waive: bool) -> Allocation` berisi `lines, penalties, titipan, selisih_transfer`
- `ap_journal(calc)` dan `ar_journal(alloc)` → `list[JournalLine(side, account, amount)]`, memunculkan `Unbalanced`

**Tes:**
- C1/02 == C1-2.
- C1-03 ≠ C1-02.
- Pembayaran 2 angsuran → S_nominal = 1.
- Aturan unggul 10 poin.
- Denda per angsuran.
- Kurang bayar ≤ 250 rb dianggap lunas.
- Jurnal Contoh A berimbang di 2.747.500.000.

### Task 4: OCR + extractor + pipeline
**Files:** `ocr.py`, `extractor.py`, `pipeline.py`, `tests/test_extractor.py`
**Produces:**
- `ocr_pdf(path) -> list[Page{n, w, h, words:[{id, text, bbox}]}]`
- `extract(pages) -> Extraction{page_types, fields: {name: {value, word_ids, confidence}}}`, dengan mode gemini/fake
- `ground(extraction, pages)` (keyakinan 0 jika tidak cocok)
- `process_termin(termin_id)`, yang memancarkan event ke `telemetry.publish(termin_id, agent, msg)`

**Tes:**
- Extractor fake pada PDF seed menghasilkan nilai yang benar.
- Grounding meng-nol-kan nilai palsu.

### Task 5: models, seed, API, mocks, auditlog
**Files:** `db.py`, `models.py`, `seed.py`, `mocks.py`, `auditlog.py`, `api.py`, `main.py`, `tests/test_api.py`
**Endpoints:**
- `GET /api/personas`, `GET /api/me`
- `GET /api/dashboard?spv=`, `GET /api/queue?spv=`
- `POST /api/ap/upload`, `GET /api/ap/termin/{id}`, `GET /api/ap/termin/{id}/pdf`, `GET /api/ap/termin/{id}/events` (SSE)
- `POST /api/ap/termin/{id}/action` dengan `{action: accept|override|post|submit_cfo|reject|flag|retry|resend, ...}`
- `GET /api/ap/contracts?spv=`
- `POST /api/ar/upload`, `GET /api/ar/receipt/{id}`, `POST /api/ar/receipt/{id}/confirm`, `GET /api/ar/units?spv=&q=`
- `GET /api/cfo/queue`, `POST /api/cfo/termin/{id}`, `POST /api/cfo/waiver/{id}`
- `GET /api/audit`, `GET /api/audit/verify`, `GET /api/outbox`, `GET /api/accuracy`, `POST /api/demo/erp_fail`

**Tes:**
- AP persona SPV-1 membaca termin SPV-2 → 403.
- Alur unggah → DISPUTE → post (Kontrak B) → POSTED dengan erp_ref.
- Kontrak A → MENUNGGU_CFO → CFO setuju → POSTED.
- Konfirmasi AR membuat jurnal dan isi Outbox.
- Verifikasi audit chain gagal setelah ada entri yang diubah.

### Task 6: Frontend
**Files:** `frontend/` (Vite React TS)
**Isi:**
- `api.ts` (fetch + header persona)
- `App.tsx` (AppBar: role switch + SPV selector + navigasi)
- Halaman `Dashboard.tsx`, `ApReview.tsx` (split-view: react-pdf + overlay bbox + tabel komparasi + Telemetry SSE + aksi), `ArReconcile.tsx`, `Cfo.tsx` (antrean, audit log + verifikasi, akurasi, outbox)

**Cek:** `npm run build` sukses, lalu FastAPI menyajikan `dist`.

### Task 7: Verifikasi
- Jalankan server (`.claude/launch.json`).
- Mainkan UJ-1, UJ-2, dan UJ-3 di browser pane.
- Perbaiki temuan, lalu tulis README dengan cara menjalankan aplikasi.
