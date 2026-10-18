# Hackathon submission draft: OmniAudit AI

## Pitch Deck

https://claude.ai/artifact/QRJ6jQud3em5jUKGaQrLJk

- 12 slides in English, with speaker notes.
- The link is still **private**. Open it and share it from the **Share** menu so judges can view it.
- If the form asks for a file, download a PDF from **Export**.
- Before submitting, fill in `[Team name]`, `[Hackathon name]` and `[team members]`.

## Deployed Prototype Link

https://omniaudit-648878449957.asia-southeast2.run.app

- No login needed. Pick a persona and an SPV at the top right.
- The interface is in Indonesian, for local finance teams.

## GitHub Repository

https://github.com/rama2990/omniaudit-ai

## Brief description

### Short (~60 words)

OmniAudit AI is an audit dashboard for multi-entity property developers. Gemini 2.5 Flash on Vertex AI reads contractor invoices, site inspection reports, tax invoices and bank statements. Deterministic code computes VAT, construction withholding tax, retention, down-payment recoupment, late penalties and balanced journals. Humans decide. Contractor overbilling is locked before payment, buyer transfers are matched to their units, and every decision lands in a tamper-evident audit trail.

### Long (~170 words)

Property developers that run each project as a separate company (SPV) leak money in both directions:
- **Outgoing:** contractors bill progress beyond the site inspection report, and retention, late penalties or down-payment recoupment get missed.
- **Incoming:** buyer transfers sit unallocated because unit codes and payer names don't match.

OmniAudit AI splits the work clearly:
- **Gemini** classifies pages and extracts fields. Every value must point to a word in the original document, so invented values are rejected.
- **Deterministic code** computes all money under Indonesian construction tax rules and runs eight anomaly checks, including overbilling and the same invoice billed to two SPVs.
- **Auditors** review in a split view that highlights the source PDF next to the claimed-versus-verified comparison.
- **The CFO** approves anything above IDR 500 million.

On the receivables side, a match score (unit code, name, amount) assigns transfers to units, computes installment late fees and sends receipts to buyers.

The prototype runs on Google Cloud Run in Jakarta, with Gemini 2.5 Flash on Vertex AI and local OCR. It has 74 automated tests and a one-week simulation of 15 scenarios, all matching expectations.
