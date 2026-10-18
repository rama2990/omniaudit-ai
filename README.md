# OmniAudit AI

**Live prototype:** https://omniaudit-648878449957.asia-southeast2.run.app (no login; pick a persona at the top right)

OmniAudit AI is an audit dashboard for property developers that run each project as a separate company (SPV). It covers:
- **Payables (AP):** checks contractor bills against the site inspection report (BAP), the contract and Indonesian construction tax rules.
- **Receivables (AR):** matches buyer payments to their units.
- **CFO:** gives the CFO control over large and suspicious cases.

How the work is split:
- **AI (Google Gemini)** only reads documents.
- **Deterministic code** computes every number: tax, retention, down payment, penalties and journals.
- **People** decide.

- Product requirements: `docs/prds/prd-omniaudit-2026-10-18/prd.md` (Indonesian)
- Technical design: `docs/superpowers/specs/2026-10-18-omniaudit-design.md`
- Cloud Run deployment: `deploy.md`

The app interface and the demo documents are in Indonesian, for local finance teams. UI labels below are quoted as they appear, with a translation.

## Running locally

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
cd frontend && npm install && npm run build && cd ..
cd backend && uv sync
uv run uvicorn app.main:app --port 8000
```

Open http://localhost:8000. On first start the database is seeded automatically. This takes about a minute because one scanned PDF goes through OCR.

**Enable Gemini:** copy `backend/.env.example` to `backend/.env` and set `GEMINI_API_KEY`. The deployed prototype uses Gemini 2.5 Flash on Vertex AI through the Cloud Run service account; see `deploy.md`. Without a key the app runs in **offline mode**, where fields are extracted with local text patterns. This is also the fallback if the network drops during a demo.

**Reset demo data:**

```bash
cd backend && uv run python -m app.seed
```

**Tests:**

```bash
cd backend && uv run pytest
```

**Check real Gemini on the demo PDFs** (needs an API key):

```bash
cd backend && uv run python scripts/gemini_check.py
```

**Frontend dev mode** (hot reload, `/api` proxied to port 8000):

```bash
cd frontend && npm run dev
```

## Demo script

All demo files are in `demo/`. Personas and SPVs are picked from the dropdowns at the top right.

**Overbilling (Dewi, Finance AP, PT Suburban Land One)**
1. Click **Unggah dokumen tagihan** (upload bill) and pick `demo/01_UJ1_kontrak_B_overbilling.pdf`.
2. The agent trail streams live. The invoice claims 60% progress but the inspection report says 55%, so the bill becomes a **Dispute**.
3. Click a pin icon in the comparison table. The PDF on the left jumps to that value.
4. Click **Terima koreksi & posting ke ERP** (accept correction and post to ERP). Verified net payable is IDR 234,562,500 and an ERP batch number appears.

**CFO case**
1. As Dewi, upload `demo/02_UJ3_kontrak_A_butuh_CFO.pdf`. The claim is IDR 2.997 billion (above IDR 500 million), so click **Ajukan ke CFO** (send to CFO).
2. Switch to Hartono (CFO) and open **Ruang CFO** (CFO room). It also holds a hard stop for an invoice billed to two SPVs.
3. Click **Tinjau** (review), then **Setujui & posting ke ERP** (approve and post). Verified net payable is IDR 2,112,875,000.
4. In the audit trail, click **Verifikasi integritas** (verify integrity), then **Simulasi ubah data** (simulate tampering) to show the hash chain breaking.

**Reconciliation (Andi, Sales Admin AR)**
1. Click **Unggah rekening koran** (upload bank statement) and pick `demo/rekening_koran_SLO1_2026-10-17.csv`. Six payments are allocated automatically by virtual account; the rest go to the queue.
2. Review the line "TRF BPK SUTRISNO BLK C1/02". It recommends unit C1-02 with a 97% score, 12 days late.
3. Tick **Hapus denda keterlambatan** (waive late fee), choose *Pencairan KPR Bank* (mortgage disbursement), add a justification, then click **Konfirmasi alokasi & kirim notifikasi ke pembeli** (confirm and notify buyer).
4. WhatsApp and email notifications with a PDF receipt appear. They are simulated; nothing is actually sent.

**Other scenarios in the seeded queue:**
- Contract D, scanned, clean: **Siap disetujui** (ready to approve).
- Contract C: retention missing and a withholding-tax rate that doesn't match the contractor's grade. Still green, with a yellow flag.
- Contract E: line items don't add up to the total.
- Contract F: inflated invoice amount.
- Contract G: the same invoice billed to two SPVs.

**Simulate an ERP failure:** click the mode chip at the top right.

## Full-run simulation

`demo/full-run/` holds a fictional work week across three SPVs:
- **12 contractor document packs** in three vendor styles: corporate letterhead with duty stamp, small contractor, and mid-size contractor. Each has an invoice, an inspection report with a weighted progress table, a Coretax-style tax invoice and progress photos. One pack is scanned.
- **3 bank statements.**

The scenarios cover:
- overbilling and a CFO case,
- the same invoice billed to two SPVs,
- an invoice rejected and then revised,
- incremental (non-cumulative) progress,
- a contract number written the vendor's own way,
- a late penalty that consumes a whole progress payment,
- an ERP failure,
- an executive waiver, partial payment, overpayment, and a payment sent by the buyer's spouse.

The step-by-step guide with expected outcomes is `demo/full-run/SKENARIO.md` (Indonesian).

**By hand in the app:** stop the server, run the command below, start the server again, and follow SKENARIO.md.

```bash
cd backend && uv run python -m app.seed --full-run
```

**Automated:** the simulator runs every step through the API and checks each outcome.

```bash
cd backend && uv run python scripts/full_run.py --offline
```

Options:
- Without `--offline` the simulator uses Gemini. One run takes 12 requests; the free tier allows about 20 per day per model.
- Add `--live` to write the results into the server's database so they show up in the app.

If Gemini fails (quota exhausted or network down), documents are read with local text patterns and the app shows a notice. Turn this off with `GEMINI_FALLBACK=0`.

## Structure

```
backend/app/   calc (tax & progress payments), audit (anomalies & status), matching (match score),
               allocation (late fees & allocation), journal, ocr, extractor (Gemini / text patterns),
               pipeline (agents + telemetry), ar, api, seed
frontend/src/  pages: Dashboard, ApReview (split view), ArReconcile, Cfo
demo/          sample bill PDFs and bank statement CSVs
docs/          requirements, design, pitch deck sources, submission draft
```
